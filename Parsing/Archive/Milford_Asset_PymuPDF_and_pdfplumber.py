import os
import fitz  # PyMuPDF
import re
import pdfplumber
import pandas as pd

# === CONFIGURATION ===
FOLDER_PATH = r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Milford_Asset\Kiwisaver_Monthly_Fact_Sheets\New Folder"
TARGET_KEYWORD = "Investment Performance after fees as at"
DATA_AREA_HEIGHT = 160
OUTPUT_EXCEL = os.path.join(FOLDER_PATH, "Combined_Performance_Data.xlsx")

# === UTILITY FUNCTIONS ===
def is_data_cell(cell):
    if cell is None:
        return False
    cell = cell.strip()
    return bool(re.match(r"^-?\d+(\.\d+)?%?$", cell) or cell in {"-", "%"})


def detect_header_row_count(rows):
    for idx, row in enumerate(rows):
        if any(is_data_cell(cell) for cell in row):
            return idx
    return 0

def detect_label_column_count(rows, header_row_count):
    data_row = rows[header_row_count]
    for idx, cell in enumerate(data_row):
        if is_data_cell(cell):
            return idx
    return 0

def normalize_table_rows(rows):
    normalized = []
    for row in rows:
        new_row = []
        skip_next = False
        for i in range(len(row)):
            if skip_next:
                skip_next = False
                continue
            current = row[i].strip()
            if i + 1 < len(row):
                next_cell = row[i + 1].strip()
                if next_cell == "%":
                    current += "%"
                    skip_next = True
                elif next_cell.endswith("%") and not current.endswith("%") and not current:
                    current = next_cell
                    skip_next = True
            new_row.append(current)
        filtered = [cell for cell in new_row if cell != ""]
        while len(filtered) < len(row):
            filtered.append("")
        normalized.append(filtered)
    return normalized

def clean_performance_data(raw_rows):
    header_row_count = detect_header_row_count(raw_rows)
    label_col_count = detect_label_column_count(raw_rows, header_row_count)
    header = []

    for col in zip(*raw_rows[:header_row_count]):
        merged = " ".join(cell.strip() for cell in col if cell.strip())
        header.append(merged)

    header = header[label_col_count:]
    output = [header]

    max_row_length = max(len(row) for row in raw_rows)
    if len(header) < max_row_length - 1:
        padding_needed = (max_row_length - 1) - len(header)
        header = [""] * padding_needed + header

    current_label = ""
    for row in raw_rows[header_row_count:]:
        label_parts = row[:label_col_count]
        combined_label = " ".join(part.strip() for part in label_parts if part.strip())
        if combined_label:
            current_label = combined_label
        data = row[label_col_count:]
        data = data[:len(header)]
        while len(data) < len(header):
            data.append("")
        output.append([current_label] + data)

    normalized_output = normalize_table_rows(output)
    return normalized_output

def extract_text_with_dict(doc, keyword):
    extracted_rows = []
    for page_num, page in enumerate(doc):
        keyword_locations = page.search_for(keyword)
        if not keyword_locations:
            continue
        for rect in keyword_locations:
            y_top = rect.y1
            y_bottom = rect.y1 + DATA_AREA_HEIGHT
            spans = []
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        y0 = span["bbox"][1]
                        y1 = span["bbox"][3]
                        if y0 >= y_top and y1 <= y_bottom:
                            spans.append({
                                "origin": (span["bbox"][0], y0),
                                "text": span["text"],
                                "size": span["size"]
                            })
            rows = group_spans_by_line(spans)
            extracted_rows.extend(rows)
    return extracted_rows

def group_spans_by_line(spans, x_tolerance=15):
    if not spans:
        return []
    spans.sort(key=lambda s: s["origin"][1])
    grouped_lines = []
    current_group = []
    current_y0 = spans[0]["origin"][1]
    current_y1 = current_y0 + 8

    for span in spans:
        y0 = span["origin"][1]
        y1 = y0 + 8
        if y0 <= current_y1:
            current_group.append(span)
            current_y1 = max(current_y1, y1)
        else:
            grouped_lines.append(current_group)
            current_group = [span]
            current_y0 = y0
            current_y1 = y1
    if current_group:
        grouped_lines.append(current_group)

    x_positions = []
    for span in spans:
        x = span["origin"][0]
        if not any(abs(x - x_ref) <= x_tolerance for x_ref in x_positions):
            x_positions.append(x)
    x_positions.sort()

    output_rows = []
    for group in grouped_lines:
        row = [""] * len(x_positions)
        for span in group:
            x = span["origin"][0]
            text = span["text"].strip()
            best_col = None
            min_dist = float("inf")
            for idx, col_x in enumerate(x_positions):
                dist = abs(x - col_x)
                if dist <= x_tolerance and dist < min_dist:
                    best_col = idx
                    min_dist = dist
            if best_col is not None:
                if row[best_col]:
                    row[best_col] += " " + text
                else:
                    row[best_col] = text
        output_rows.append(row)
    return output_rows


def extract_table_with_pdfplumber(pdf_path, keyword):

    doc = fitz.open(pdf_path)

    for page_num, page in enumerate(doc):
        keyword_locations = page.search_for(keyword)
        if not keyword_locations:
            continue

        for rect in keyword_locations:
            y_top = rect.y1
            y_bottom = y_top + DATA_AREA_HEIGHT

            # Now open same page in pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                pl_page = pdf.pages[page_num]

                # Crop using keyword-based region
                cropped = pl_page.crop((0, y_top, pl_page.width, y_bottom))

                try:
                    tables = cropped.extract_tables({
                                                    "vertical_strategy": "text",
                                                    "horizontal_strategy": "text",
                                                    "snap_tolerance":2, 
                                                     "join_tolerance": 0.3,
                                                     "text_x_tolerance": 1,
                                                    "text_y_tolerance": 3,
                                                    "edge_min_length": 3,
                                                    "intersection_tolerance": 5,})
                    if tables:
                        return tables[0]
                except Exception as e:
                    print(f"pdfplumber error: {e}")
                    continue

    return None

def sanitize_table(table):
    return [[cell.strip() if cell else "" for cell in row] for row in table]

def process_pdf(pdf_path):
    # Try pdfplumber first
    print(f"Trying pdfplumber for: {pdf_path}")
    table = extract_table_with_pdfplumber(pdf_path, TARGET_KEYWORD)
    if table:
        print("Extracted using pdfplumber.")
        table = sanitize_table(table)
        return clean_performance_data(table)

    # Fallback to fitz
    print("Falling back to PyMuPDF extraction.")
    doc = fitz.open(pdf_path)
    raw_text = extract_text_with_dict(doc, TARGET_KEYWORD)
    return clean_performance_data(raw_text)


def main():
    all_data = {}
    for file in os.listdir(FOLDER_PATH):
        if file.lower().endswith(".pdf"):
            pdf_path = os.path.join(FOLDER_PATH, file)
            print(f"\nProcessing: {pdf_path}")
            rows = process_pdf(pdf_path)
            df = pd.DataFrame(rows)

            sheet_title = os.path.splitext(file)[0]
            sheet_title_parts = sheet_title.split('_')
            sheet_name = "_".join(sheet_title_parts[1:])[:31] if len(sheet_title_parts) > 1 else sheet_title[:31]

            all_data[sheet_name] = df

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        for sheet_name, df in all_data.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

    print(f"\n✅ Data saved to: {OUTPUT_EXCEL}")


if __name__ == "__main__":
    main()

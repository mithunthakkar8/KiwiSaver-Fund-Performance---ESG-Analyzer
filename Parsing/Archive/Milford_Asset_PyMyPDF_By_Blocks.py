import os
import fitz  # PyMuPDF
import re
import collections
import pandas as pd
from pprint import pprint

# === CONFIGURATION ===
FOLDER_PATH = r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Fisher_Funds\Kiwisaver"
TARGET_KEYWORD = "Top 10 investments"
X_TOLERANCE = 5
COLUMN_AREA_HEIGHT = 40
COLUMN_AREA_WIDTH = 400
DATA_AREA_HEIGHT = 150
DATA_AREA_WIDTH = 300
OUTPUT_EXCEL = os.path.join(FOLDER_PATH, "Combined_Performance_Data.xlsx")

# === UTILITY FUNCTIONS ===

def is_numeric_or_percentage(value):
    """Check if a string is a number or a percentage."""
    return bool(re.match(r'^-?$|^-?\d+(\.\d+)?%?$', value.strip()))


def group_text_by_x(spans, x_tolerance=X_TOLERANCE):
    """Group text spans by similar x-coordinates (within tolerance)."""
    grouped = collections.defaultdict(list)
    for span in spans:
        x = span['origin'][0]
        text = span['text'].strip()
        if not text:
            continue

        matched_key = None
        for key in grouped:
            if abs(x - key) <= x_tolerance:
                matched_key = key
                break

        if matched_key is not None:
            grouped[matched_key].append((x, text))
        else:
            grouped[x].append((x, text))

    final_columns = [
        " ".join([txt for _, txt in sorted(items)]) for items in sorted(grouped.values(), key=lambda group: group[0][0])
    ]
    return final_columns


def extract_raw_blocks(doc, keyword):
    """Extract nearby text blocks following a keyword."""
    raw_output_lines = []

    for page_num, page in enumerate(doc):
        print(f"\n--- Page {page_num + 1} ---")
        keyword_locations = page.search_for(keyword, quads=False)

        if keyword_locations:
            for rect in keyword_locations:
                print(f"Found '{keyword}' at: {rect}")
                area_below = fitz.Rect(
                    rect.x0,
                    rect.y1,
                    rect.x1 + DATA_AREA_WIDTH,
                    rect.y1 + DATA_AREA_HEIGHT
                )
                text_dict = page.get_text("dict")
                for block in text_dict["blocks"]:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_rect = fitz.Rect(span["bbox"])
                            if area_below.intersects(span_rect):
                                text = span["text"].strip()
                                if text or text == "-": # include dashes
                                    raw_output_lines.append(f"→ {text}")
        else:
            print(f"No match for '{keyword}'")

    return "\n".join(raw_output_lines)


def parse_blocks_cleanly(raw_text):
    """Convert extracted blocks into structured label-value pairs."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    results = []
    current_label = None
    current_content = []

    for line in lines:
        if line.startswith("→"):
            if current_label:
                label, content = current_label, current_content
                if all(not is_numeric_or_percentage(val) for val in [label] + content):
                    results.append({"Label": "Column_Names", "Content": [label] + content})
                else:
                    numeric_only = [val for val in content if is_numeric_or_percentage(val)]
                    if numeric_only:
                        results.append({"Label": label, "Content": numeric_only})
            current_label = line[1:].strip()
            current_content = []
        else:
            current_content.append(line)

    if current_label:
        if all(not is_numeric_or_percentage(val) for val in [current_label] + current_content):
            results.append({"Label": "column_values", "Content": [current_label] + current_content})
        else:
            numeric_only = [val for val in current_content if is_numeric_or_percentage(val)]
            if numeric_only:
                results.append({"Label": current_label, "Content": numeric_only})

    return results

def merge_column_name_rows(data):
    merged_columns = ['Column_Names']
    new_data = []

    for row in data:
        if row[0] == 'Column_Names':
            merged_columns.extend(row[1:])
        else:
            new_data.append(row)

    # Place merged column names at the top
    return [merged_columns] + new_data


def process_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    raw_text = extract_raw_blocks(doc, TARGET_KEYWORD)
    parsed = parse_blocks_cleanly(raw_text)
    rows = []
    for item in parsed:
        label = item["Label"]
        row = [label] + item["Content"]
        rows.append(row)
    return rows

def main():
    all_data = {}
    for file in os.listdir(FOLDER_PATH):
        if file.lower().endswith(".pdf"):
            pdf_path = os.path.join(FOLDER_PATH, file)
            print(f"Processing: {pdf_path}")
            rows = process_pdf(pdf_path)
            cleaned_rows = merge_column_name_rows(rows)            
            df = pd.DataFrame(cleaned_rows)

            # Generate sheet name by skipping the first word
            sheet_title = os.path.splitext(file)[0]
            sheet_title_parts = []
            for part in sheet_title.split('_'):
                sheet_title_parts.extend(part.split(' '))
            sheet_name = "_".join(sheet_title_parts[1:])[:31] if len(sheet_title_parts) > 1 else sheet_title[:31]

            all_data[sheet_name] = df

    # Write all data to Excel file
    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        for sheet_name, df in all_data.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

    print(f"\nData saved to: {OUTPUT_EXCEL}")


if __name__ == "__main__":
    main()
import os
import fitz  # PyMuPDF
import re
import pandas as pd
from calendar import month_name


class Numeric_Data_PDF_Parser:
    def __init__(self, folder_path, terms_to_search, data_area_height=160, data_area_width=595, \
                  validation_file = "Validation.xlsx", x_tolerance = 20, y_tolerance = 8):
        self.folder_path = folder_path
        # self.keyword = keyword
        self.data_area_height = data_area_height
        self.data_area_width = data_area_width
        self.output_excel = os.path.join(self.folder_path, validation_file)
        self.all_data = {}
        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance
        self.terms_to_search = terms_to_search

    @staticmethod
    def is_data_cell(cell):
        cell = cell.strip()
        return bool(re.match(r"^-?\d+(\.\d+)?%?$", cell) or cell in {"-", "%"})

    def detect_header_row_count(self, rows):
        for idx, row in enumerate(rows):
            if any(self.is_data_cell(cell) for cell in row):
                return idx
        return 0

    def detect_label_column_count(self, rows, header_row_count):
        data_row = rows[header_row_count]
        for idx, cell in enumerate(data_row):
            if self.is_data_cell(cell):
                return idx
        return 0

    @staticmethod
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
            # while len(filtered) < len(row):
            #     filtered.append("")
            normalized.append(filtered)

        return normalized

    def clean_performance_data(self, raw_rows):
        header_row_count = self.detect_header_row_count(raw_rows)
        label_col_count = self.detect_label_column_count(raw_rows, header_row_count)

        header = []
        for col in zip(*raw_rows[:header_row_count]):
            merged = " ".join(cell.strip() for cell in col if cell.strip())
            header.append(merged)
        header = [item for item in header if item.strip() != '']

        output = [header]
        current_label = ""
        for row in raw_rows[header_row_count:]:
            label_parts = row[:label_col_count]
            combined_label = " ".join(part.strip() for part in label_parts if part.strip())
            if combined_label:
                current_label = combined_label

            data = row[label_col_count:]
            output.append([current_label] + data)

        normalized_output = self.normalize_table_rows(output)
        max_row_length = max(len(row) for row in normalized_output)
        if len(normalized_output[0]) < max_row_length:
            padding_needed = max_row_length - len(normalized_output[0])
            header = [""] * padding_needed + normalized_output[0]

        normalized_output[0] = header
        return normalized_output

    def group_spans_by_line(self, spans):
        if not spans:
            return []

        spans.sort(key=lambda s: s["origin"][1])
        grouped_lines = []
        current_group = []
        current_y0 = spans[0]["origin"][1]
        current_y1 = current_y0 + self.y_tolerance

        for span in spans:
            y0 = span["origin"][1]
            y1 = y0 + self.y_tolerance
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
            if not any(abs(x - x_ref) <= self.x_tolerance for x_ref in x_positions):
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
                    if dist <= self.x_tolerance and dist < min_dist:
                        best_col = idx
                        min_dist = dist
                if best_col is not None:
                    if row[best_col]:
                        row[best_col] += "" + text.strip()
                    else:
                        row[best_col] = text.strip()
            output_rows.append(row)

        return output_rows

    def extract_text_with_dict(self, doc):
        extracted_rows = []

        for page_num, page in enumerate(doc):
            for term in self.terms_to_search:
                print(f"\n--- Page {page_num + 1} ---")
                keyword_locations = page.search_for(term)
                if not keyword_locations:
                    print(f"No match for '{term}'")
                    continue

                for rect in keyword_locations:
                    print(f"Found '{term}' at: {rect}")
                    x_left = rect.x0
                    x_right = rect.x0 + self.data_area_width
                    
                    y_top = rect.y1
                    y_bottom = rect.y1 + self.data_area_height

                    # print(f"x_left: {x_left}" )
                    # print(f"x_right:{x_right}")
                    # print(f"y_top: {y_top}")
                    # print(f"y_bottom: {y_bottom}")

                    spans = []
                    blocks = page.get_text("dict")["blocks"]
                    for block in blocks:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                x0, y0, x1, y1 = span["bbox"]
                                # print(f"SPAN: {span['text']}, BBOX: {span['bbox']}")
                                if y0 >= round(y_top) and y1 <= round(y_bottom) and x0 >= round(x_left) and x1 <= round(x_right):
                                    # print(f"Captured: {span['text']}, SPAN: {span['bbox']}")
                                    spans.append({
                                        "origin": (x0, y0),
                                        "text": span["text"],
                                        "size": span["size"]
                                    })


                    rows = self.group_spans_by_line(spans)
                    extracted_rows.extend(rows)

        return extracted_rows

    def process_pdf(self, pdf_path):
        doc = fitz.open(pdf_path)
        raw_text = self.extract_text_with_dict(doc)
        if not raw_text:
            return None
        return self.clean_performance_data(raw_text)

    def convert_month_to_short(self, name):
        month_map = {m.lower(): m[:3] for m in month_name if m}
        for full, short in month_map.items():
            if full in name.lower():
                return name.lower().replace(full, short).title()
        return name

    def validate_and_export(self):
        for file in os.listdir(self.folder_path):
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(self.folder_path, file)
                print(f"Processing: {pdf_path}")
                rows = self.process_pdf(pdf_path)
                if rows is None:
                    print(f"Skipping {file}: No data extracted.")
                    continue
                df = pd.DataFrame(rows)

                sheet_title = os.path.splitext(file)[0]
                sheet_title_parts = []
                for part in sheet_title.split('_'):
                    sheet_title_parts.extend(part.split(' '))
                if len(sheet_title_parts) > 1:
                    month_adjusted = self.convert_month_to_short(sheet_title_parts[-2])
                    sheet_title_parts[-2] = month_adjusted
                sheet_title_parts = [x for x in sheet_title_parts if x not in ['Fund', 'fund', 'Update', 'update', 'Updates']]
                sheet_name = "".join(sheet_title_parts)

                self.all_data[sheet_name[:31]] = df

        if self.all_data:
            with pd.ExcelWriter(self.output_excel, engine="openpyxl") as writer:
                for sheet_name, df in self.all_data.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

            print(f"\nData saved to: {self.output_excel}")


if __name__ == "__main__":
    # extractor = Numeric_Data_PDF_Parser(
    #     folder_path=r"C:\\Users\\mithu\\Documents\\MEGA\\Projects\\KiwiSaver Fund Performance & ESG Analyzer\\Downloads\\Milford_Asset\\Kiwisaver_Monthly_Fact_Sheets",
    #     terms_to_search =["Investment Performance after fees as at"],
    #     data_area_height=160, data_area_width=595,
    #     validation_file = "Combined_Performance_Data.xlsx",
    #     x_tolerance=30
    # )
    # extractor.validate_and_export()

    # extractor = Numeric_Data_PDF_Parser(
    #     folder_path=r"C:\\Users\\mithu\\Documents\\MEGA\\Projects\\KiwiSaver Fund Performance & ESG Analyzer\\Downloads\\Milford_Asset\\Kiwisaver_Monthly_Fact_Sheets",
    #     terms_to_search = ["Top Equity Holdings", "Top Security Holdings"],
    #     data_area_height=205, data_area_width=255,
    #     validation_file = "Equity_Holdings_Data.xlsx",
    #     x_tolerance=20
    # )
    # extractor.validate_and_export()

    # extractor = Numeric_Data_PDF_Parser(
    #     folder_path=r"C:\\Users\\mithu\\Documents\\MEGA\\Projects\\KiwiSaver Fund Performance & ESG Analyzer\\Downloads\\Milford_Asset\\Kiwisaver_Monthly_Fact_Sheets\\New Folder",
    #     terms_to_search = ["Sector Allocation"],
    #     data_area_height=220, data_area_width=255,
    #     validation_file = "Sector_Allocation.xlsx",
    #     x_tolerance=20
    # )
    # extractor.validate_and_export()

    # extractor = Numeric_Data_PDF_Parser(
    #     folder_path=r"C:\\Users\\mithu\\Documents\\MEGA\\Projects\\KiwiSaver Fund Performance & ESG Analyzer\\Downloads\\Milford_Asset\\Kiwisaver_Monthly_Fact_Sheets\\New Folder",
    #     terms_to_search = ["Current Asset Allocation"],
    #     data_area_height=220, data_area_width=350,
    #     validation_file = "Current_Asset_Allocation.xlsx",
    #     x_tolerance=20
    # )
    # extractor.validate_and_export()

    # extractor = Numeric_Data_PDF_Parser(
    #     folder_path=r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Milford_Asset\Investment_Funds_Fact_Sheets\New Folder",
    #     terms_to_search = ["Current Asset Allocation"],
    #     data_area_height=220, data_area_width=350,
    #     validation_file = "Current_Asset_Allocation.xlsx",
    #     x_tolerance=20
    # )
    # extractor.validate_and_export()


    extractor = Numeric_Data_PDF_Parser(
        folder_path=r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Fisher_Funds\Kiwisaver\New Folder",
        terms_to_search = ["Top 10 investments"],
        data_area_height=600, data_area_width=500,
        validation_file = "Top_10_investments.xlsx",
        x_tolerance=20,
        y_tolerance=8
    )
    extractor.validate_and_export()

    # extractor = Numeric_Data_PDF_Parser(
    #     folder_path=r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Simplicity\KiwiSaver",
    #     terms_to_search = ["Top 10 investments"],
    #     data_area_height=600, data_area_width=500,
    #     validation_file = "Top_10_investments.xlsx",
    #     x_tolerance=20,
    #     y_tolerance=8
    # )
    # extractor.validate_and_export()
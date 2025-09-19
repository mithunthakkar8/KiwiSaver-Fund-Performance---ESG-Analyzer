import os
import re
import fitz  # PyMuPDF
import camelot
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from sklearn.cluster import DBSCAN
from calendar import month_name
from functools import wraps

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_parser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_exceptions(func):
    """Decorator to log exceptions and provide basic error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            logger.info(f"Starting {func.__name__}")
            result = func(*args, **kwargs)
            logger.info(f"Completed {func.__name__} successfully")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            raise  # Re-raise the exception after logging
    return wrapper

class Numeric_Data_PDF_Parser:
    def __init__(self, folder_path, terms_to_search, validation_file="Validation.xlsx", 
                 x_tolerance=20, y_tolerance=8, data_area_height=160, data_area_width=595):
        """Initialize the PDF parser with configuration parameters"""
        try:
            logger.info(f"Initializing Numeric_Data_PDF_Parser with folder: {folder_path}")
            self.folder_path = folder_path
            self.terms_to_search = terms_to_search
            self.output_excel = os.path.join(self.folder_path, validation_file)
            self.all_data = {}
            self.x_tolerance = x_tolerance
            self.y_tolerance = y_tolerance
            self.data_area_height = data_area_height
            self.data_area_width = data_area_width
            
            # Validate parameters
            if not os.path.isdir(self.folder_path):
                raise ValueError(f"Folder path does not exist: {self.folder_path}")
            if not self.terms_to_search:
                raise ValueError("No search terms provided")
                
            logger.info("Initialization completed successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PDF parser: {str(e)}")
            raise

    @log_exceptions
    def get_file_year(self, filename):
        """Extract year from filename (last 4 digits before .pdf)"""
        try:
            match = re.search(r'(\d{4})\.pdf$', filename, re.IGNORECASE)
            if not match:
                logger.warning(f"No year found in filename: {filename}")
                return None
            year = int(match.group(1))
            logger.debug(f"Extracted year {year} from filename {filename}")
            return year
        except Exception as e:
            logger.error(f"Error extracting year from filename {filename}: {str(e)}")
            return None

    # ========== DBSCAN METHODS (For pre-2024 files) ==========
    @log_exceptions
    def group_spans(self, spans):
        """Group text spans from PDF into a structured table using DBSCAN clustering."""
        try:
            if not spans:
                logger.debug("No spans provided to group_spans")
                return []

            # ===== 0. Filter out tiny text spans =====
            if len(spans) > 1:
                font_sizes = [span.get("size", 0) for span in spans]
                median_size = np.median(font_sizes)
                spans = [
                    span for span in spans 
                    if span.get("size", 0) > 0.8 * median_size
                ]
                logger.debug(f"Filtered spans from {len(font_sizes)} to {len(spans)} based on font size")

            points = np.array([(span["origin"][0], span["origin"][1]) for span in spans])
            
            # ===== 1. Cluster spans into rows =====
            row_dbscan = DBSCAN(eps=self.y_tolerance, min_samples=1)
            row_labels = row_dbscan.fit_predict(points[:, 1].reshape(-1, 1))
            logger.debug(f"Row clustering completed with {len(set(row_labels))} rows found")

            # Group spans by their row cluster labels
            rows = {}
            for span, label in zip(spans, row_labels):
                if label not in rows:
                    rows[label] = []
                rows[label].append(span)
            
            sorted_rows = sorted(rows.items(), key=lambda x: np.mean([span["origin"][1] for span in x[1]]))
            
            # ===== 2. Cluster spans into columns ===== 
            column_dbscan = DBSCAN(eps=self.x_tolerance, min_samples=1)
            column_labels = column_dbscan.fit_predict(points[:, 0].reshape(-1, 1))
            logger.debug(f"Column clustering completed with {len(set(column_labels))} columns found")

            x_positions = {}
            for x, label in zip(points[:, 0], column_labels):
                if label not in x_positions:
                    x_positions[label] = []
                x_positions[label].append(x)
            
            x_positions = sorted([np.mean(cluster) for cluster in x_positions.values()])
            
            # ===== 3. Build table structure =====
            table = []
            for _, spans_in_row in sorted_rows:
                row = [""] * len(x_positions)
                cell_spans = {}

                # Define bottom boundary of table
                if any("currency hedging" in span["text"].lower() or \
                      span["text"].strip().lower().startswith(("https://", "www.")) \
                      for span in spans_in_row):
                    logger.debug("Found table boundary marker, ending table construction")
                    break
                
                for span_idx, span in enumerate(spans_in_row):
                    x = span["origin"][0]
                    closest_col = min(range(len(x_positions)), key=lambda i: abs(x - x_positions[i]))
                    if abs(x - x_positions[closest_col]) <= self.x_tolerance:
                        if closest_col not in cell_spans:
                            cell_spans[closest_col] = []
                        cell_spans[closest_col].append(span)

                for col, spans_in_cell in cell_spans.items():
                    spans_in_cell.sort(key=lambda s: (s["origin"][0], s["origin"][1]))
                    merged_text = " ".join(span["text"].strip() for span in spans_in_cell)
                    row[col] = merged_text

                if any(cell.strip() for cell in row):
                    table.append(row)

            logger.info(f"Built table with {len(table)} rows and {len(x_positions)} columns")
            return table

        except Exception as e:
            logger.error(f"Error in group_spans: {str(e)}")
            return []

    @log_exceptions
    def extract_with_dbscan(self, doc):
        """Extract text using DBSCAN approach"""
        try:
            extracted_rows = []
            logger.info(f"Starting DBSCAN extraction with {len(doc)} pages")
            
            for page_num, page in enumerate(doc):
                for term in self.terms_to_search:
                    keyword_locations = page.search_for(term)
                    if not keyword_locations:
                        logger.debug(f"Term '{term}' not found on page {page_num + 1}")
                        continue
                            
                    for rect in keyword_locations:
                        spans = []
                        blocks = page.get_text("dict")["blocks"]
                        for block in blocks:
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    x0, y0, x1, y1 = span["bbox"]
                                    if (x0 >= rect.x0 and x1 <= rect.x0 + self.data_area_width and
                                        y0 >= rect.y1 and y1 <= rect.y1 + self.data_area_height):
                                        spans.append({
                                            "origin": (x0, y0),
                                            "text": span["text"],
                                            "size": span["size"]
                                        })

                        if spans:
                            logger.debug(f"Found {len(spans)} spans for term '{term}' on page {page_num + 1}")
                            rows = self.group_spans(spans)
                            if rows and len(rows) > 0:
                                ref_row = rows[0]
                                filtered_rows = [ref_row]
                                for row in rows[1:]:
                                    if len(row) >= len(ref_row) // 2:
                                        filtered_rows.append(row)
                                extracted_rows.extend(filtered_rows)
                                logger.debug(f"Added {len(filtered_rows)} rows from term '{term}'")

            logger.info(f"DBSCAN extraction completed with {len(extracted_rows)} total rows")
            return extracted_rows
        except Exception as e:
            logger.error(f"Error in extract_with_dbscan: {str(e)}")
            return []

    # ========== CAMELOT METHODS (For 2024+ files) ==========
    @staticmethod
    @log_exceptions
    def is_data_cell(cell):
        """Check if cell contains numeric data"""
        try:
            cell = cell.strip()
            is_data = bool(re.match(r"^-?\d+(\.\d+)?%?$", cell) or cell in {"-", "%"})
            logger.debug(f"Cell '{cell}' is_data: {is_data}")
            return is_data
        except Exception as e:
            logger.error(f"Error in is_data_cell: {str(e)}")
            return False

    @log_exceptions
    def detect_header_row_count(self, rows):
        """Detect number of header rows"""
        try:
            for idx, row in enumerate(rows):
                if any(self.is_data_cell(cell) for cell in row):
                    logger.debug(f"Detected {idx} header rows")
                    return idx
            logger.debug("No header rows detected")
            return 0
        except Exception as e:
            logger.error(f"Error in detect_header_row_count: {str(e)}")
            return 0

    @log_exceptions
    def detect_label_column_count(self, rows, header_row_count):
        """Detect number of label columns"""
        try:
            if not rows or header_row_count >= len(rows):
                logger.warning("Invalid rows or header_row_count in detect_label_column_count")
                return 0
                
            data_row = rows[header_row_count]
            for idx, cell in enumerate(data_row):
                if self.is_data_cell(cell):
                    logger.debug(f"Detected {idx} label columns")
                    return idx
            logger.debug("No label columns detected")
            return 0
        except Exception as e:
            logger.error(f"Error in detect_label_column_count: {str(e)}")
            return 0

    @staticmethod
    @log_exceptions
    def normalize_table_rows(rows):
        """Normalize table rows (merge percentage signs, etc.)"""
        try:
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
                normalized.append(filtered)
            logger.debug(f"Normalized {len(rows)} rows to {len(normalized)} rows")
            return normalized
        except Exception as e:
            logger.error(f"Error in normalize_table_rows: {str(e)}")
            return rows if rows else []

    @log_exceptions
    def clean_extracted_table(self, data, source_type='camelot'):
        """Process table by cleaning and restructuring data"""
        try:
            logger.info(f"Starting table cleaning (source: {source_type})")
            
            if source_type == 'camelot':
                raw_rows = data.values.tolist() if isinstance(data, pd.DataFrame) else data
            else:
                raw_rows = data

            if not raw_rows:
                logger.warning("No data provided to clean_extracted_table")
                return []

            # ===== 1. Remove any rows containing our search terms =====
            rows = [
                row for row in raw_rows
                if not any(
                    term.lower() in str(cell).lower()
                    for term in self.terms_to_search
                    for cell in row
                )
            ]
            logger.debug(f"Filtered {len(raw_rows) - len(rows)} term-containing rows")

            # ===== 2. Find % of funds column =====
            percent_funds_col = -1
            for row in rows:
                for i, cell in enumerate(row):
                    cell_text = str(cell).strip()
                    if cell_text and re.match(r'^\d*\.?\d+%$', cell_text):
                        percent_funds_col = i
                        break
                if percent_funds_col != -1:
                    break
            logger.debug(f"Percentage funds column: {percent_funds_col}")

            # ===== 3. Merge continuation rows =====
            processed_rows = []
            for row in rows:
                if source_type == 'dbscan':
                    str_row = row
                else:
                    str_row = [str(cell).strip() for cell in row]
                
                is_continuation = (
                    (percent_funds_col == -1 or 
                        (percent_funds_col < len(str_row) and not str_row[percent_funds_col]))
                )

                if is_continuation and processed_rows:
                    previous_row = processed_rows[-1]
                    for i in range(min(len(previous_row), len(str_row))):
                        if str_row[i] and not previous_row[i].endswith(str_row[i]):
                            previous_row[i] = f"{previous_row[i]} {str_row[i]}".strip()
                else:
                    processed_rows.append(str_row)
            logger.debug(f"Merged rows to {len(processed_rows)} total rows")

            # ===== 4. Detect header rows =====
            header_row_count = self.detect_header_row_count(processed_rows)
            logger.debug(f"Detected {header_row_count} header rows")

            # ===== 5. Process headers (with term removal) =====
            final_output = []
            if header_row_count > 0:
                header = []
                for col in zip(*processed_rows[:header_row_count]):
                    merged = " ".join(cell for cell in col if cell).strip()
                    for term in self.terms_to_search:
                        merged = re.sub(re.escape(term), '', merged, flags=re.IGNORECASE)
                    header.append(merged.strip())
                final_output.append([h for h in header])  
            
            # ===== 6. Add cleaned data rows =====
            final_output.extend(processed_rows[header_row_count:])
            
            # ===== 7. Remove empty columns by shifting data left =====
            if final_output:
                empty_cols = []
                for col_idx in range(len(final_output[0])):
                    if all(len(row) <= col_idx or not str(row[col_idx]).strip() for row in final_output):
                        empty_cols.append(col_idx)
                
                if empty_cols:
                    new_output = []
                    for row in final_output:
                        new_row = [cell for i, cell in enumerate(row) if i not in empty_cols]
                        new_output.append(new_row)
                    final_output = new_output
                    logger.debug(f"Removed {len(empty_cols)} empty columns")
                
            # ===== 7.1: Process header row separately =====
            if final_output and len(final_output) > 0:
                header_row = final_output[0]
                empty_header_cols = [
                    i for i in range(len(header_row)) 
                    if i != 0 and not str(header_row[i]).strip()
                ]
                
                if empty_header_cols:
                    new_header = [header_row[0]]
                    for i in range(1, len(header_row)):
                        if i not in empty_header_cols:
                            new_header.append(header_row[i])
                    final_output[0] = new_header
                    logger.debug(f"Cleaned {len(empty_header_cols)} empty header columns")

            # ===== 7.2: Process data rows for completely empty columns =====
            if len(final_output) > 1:
                empty_data_cols = []
                num_cols = max(len(row) for row in final_output[1:])
                
                for col_idx in range(num_cols):
                    if all(
                        len(row) <= col_idx or not str(row[col_idx]).strip() 
                        for row in final_output[1:]
                    ):
                        empty_data_cols.append(col_idx)
                
                if empty_data_cols:
                    new_output = [final_output[0]]
                    for row in final_output[1:]:
                        new_row = [
                            cell for i, cell in enumerate(row) 
                            if i not in empty_data_cols
                        ]
                        new_output.append(new_row)
                    final_output = new_output
                    logger.debug(f"Removed {len(empty_data_cols)} empty data columns")

            # ===== 9. Clean first column integers with text fragments =====
            if len(final_output) > 1:
                integer_count = 0
                total_cells = 0
                
                for row in final_output[1:]:
                    if len(row) > 0:
                        total_cells += 1
                        first_cell = str(row[0]).strip()
                        if first_cell and first_cell.split()[0].isdigit():
                            integer_count += 1
                
                if total_cells > 0 and integer_count / total_cells > 0.8:
                    for row in final_output[1:]:
                        if len(row) > 0:
                            first_cell = str(row[0]).strip()
                            parts = first_cell.split()
                            if parts and parts[0].isdigit() and len(parts) > 1:
                                row[0] = parts[0]
                                if len(row) > 1:
                                    row[1] = ' '.join(parts[1:]) + (' ' + row[1] if row[1] else '')
                                else:
                                    row.append(' '.join(parts[1:]))
                    logger.debug("Cleaned integer/text fragments in first column")

            logger.info(f"Table cleaning completed. Final table size: {len(final_output)} rows")
            return final_output
        except Exception as e:
            logger.error(f"Error in clean_extracted_table: {str(e)}")
            return []
        
        
    @log_exceptions
    def extract_with_camelot(self, pdf_path):
        """Extract tables using Camelot"""
        try:
            logger.info(f"Starting Camelot extraction for {pdf_path}")
            tables = camelot.read_pdf(pdf_path, flavor='stream', pages='all')
            processed_tables = []
            
            for table in tables:
                table_text = ' '.join(table.df.values.flatten().tolist()).lower()
                if any(kw.lower() in table_text for kw in self.terms_to_search):
                    logger.debug(f"Found table with search terms: {table_text[:100]}...")
                    cleaned_table = self.clean_extracted_table(table.df, source_type='camelot')
                    processed_tables.append(cleaned_table)
            
            logger.info(f"Camelot extraction completed with {len(processed_tables)} relevant tables")
            return processed_tables
        except Exception as e:
            logger.error(f"Error in extract_with_camelot for {pdf_path}: {str(e)}")
            return []

    # ========== MAIN PROCESSING METHODS ==========
    @log_exceptions
    def process_pdf(self, pdf_path):
        """Process PDF based on its year"""
        try:
            filename = os.path.basename(pdf_path)
            logger.info(f"Processing PDF: {filename}")
            
            year = self.get_file_year(filename)
            
            if year and year >= 2024:
                logger.info(f"Using Camelot for {filename} (year: {year})")
                tables = self.extract_with_camelot(pdf_path)
                return tables[0] if tables else None
            else:
                logger.info(f"Using DBSCAN for {filename} (year: {year if year else 'unknown'})")
                doc = fitz.open(pdf_path)
                raw_text = self.extract_with_dbscan(doc)
                if raw_text:
                    return self.clean_extracted_table(raw_text, source_type='dbscan')
                return None
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            return None

    @log_exceptions
    def identify_header_rows(self, raw_rows):
        """Legacy header identification for DBSCAN data"""
        try:
            if not raw_rows:
                logger.warning("No rows provided to identify_header_rows")
                return [], 0

            def is_data_cell(cell):
                cell = cell.strip()
                return bool(re.match(r"^-?\d+(\.\d+)?%?$", cell) or cell in {"-", "%"})

            data_start_index = 0
            for idx, row in enumerate(raw_rows):
                if any(is_data_cell(cell) for cell in row):
                    data_start_index = idx
                    break

            header_rows = raw_rows[:data_start_index]
            if not header_rows and raw_rows:
                header_rows = [raw_rows[0]]
                data_start_index = 1

            logger.debug(f"Identified {len(header_rows)} header rows")
            return header_rows, data_start_index
        except Exception as e:
            logger.error(f"Error in identify_header_rows: {str(e)}")
            return [], 0

    @log_exceptions
    def convert_month_to_short(self, name):
        """Convert month names to short form"""
        try:
            month_map = {m.lower(): m[:3] for m in month_name if m}
            for full, short in month_map.items():
                if full in name.lower():
                    result = name.lower().replace(full, short).title()
                    logger.debug(f"Converted month {name} to {result}")
                    return result
            return name
        except Exception as e:
            logger.error(f"Error in convert_month_to_short: {str(e)}")
            return name

    @log_exceptions
    def validate_and_export(self):
        """Main processing method"""
        try:
            logger.info(f"Starting validation and export for folder: {self.folder_path}")
            
            if not os.path.exists(self.folder_path):
                raise FileNotFoundError(f"Folder not found: {self.folder_path}")

            processed_files = 0
            for file in os.listdir(self.folder_path):
                if file.lower().endswith(".pdf"):
                    pdf_path = os.path.join(self.folder_path, file)
                    logger.info(f"Processing file: {file}")
                    
                    try:
                        data = self.process_pdf(pdf_path)
                        if data is None:
                            logger.warning(f"No data extracted from {file}")
                            continue
                        
                        df = pd.DataFrame(data)

                        # Process sheet name
                        sheet_title = os.path.splitext(file)[0]
                        sheet_title_parts = []
                        for part in sheet_title.split('_'):
                            sheet_title_parts.extend(part.split(' '))
                        
                        if len(sheet_title_parts) > 1:
                            month_adjusted = self.convert_month_to_short(sheet_title_parts[-2])
                            sheet_title_parts[-2] = month_adjusted
                        
                        sheet_title_parts = [
                            re.sub(r'kiwisaver', 'KS', part, flags=re.IGNORECASE)
                            for part in sheet_title_parts
                            if part not in ['Fund', 'fund', 'Update', 'update', 'Updates']
                        ]
                        sheet_name = "".join(sheet_title_parts[:31])

                        self.all_data[sheet_name] = df
                        processed_files += 1
                        logger.info(f"Successfully processed {file} as sheet {sheet_name}")

                    except Exception as e:
                        logger.error(f"Error processing file {file}: {str(e)}")
                        continue

            if self.all_data:
                logger.info(f"Exporting {len(self.all_data)} sheets to {self.output_excel}")
                try:
                    with pd.ExcelWriter(self.output_excel, engine="openpyxl") as writer:
                        for sheet_name, df in self.all_data.items():
                            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                            
                            # Access the worksheet and set column widths
                            worksheet = writer.sheets[sheet_name]
                            for column in worksheet.columns:
                                column_letter = column[0].column_letter
                                worksheet.column_dimensions[column_letter].width = 20
                    
                    logger.info(f"Successfully exported data to {self.output_excel}")
                    print(f"\nData saved to: {self.output_excel}")
                except Exception as e:
                    logger.error(f"Error exporting to Excel: {str(e)}")
                    raise

            logger.info(f"Processing completed. {processed_files} files processed successfully")
            return processed_files > 0
        except Exception as e:
            logger.error(f"Error in validate_and_export: {str(e)}")
            return False

if __name__ == "__main__":
    try:
        logger.info("Starting PDF parser application")
        
        extractor = Numeric_Data_PDF_Parser(
            folder_path=r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Fisher_Funds\Kiwisaver",
            terms_to_search=["Top 10 investments"],
            validation_file="Top_10_investments.xlsx",
            x_tolerance=10,
            y_tolerance=10,
            data_area_height=600,
            data_area_width=500
        )
        
        success = extractor.validate_and_export()
        if not success:
            logger.warning("No data was processed successfully")
        
        logger.info("PDF parser application completed")
    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
        raise
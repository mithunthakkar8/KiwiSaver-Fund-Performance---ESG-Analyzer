import pdfplumber
from pathlib import Path
import fitz  # PyMuPDF
import numpy as np
import calendar
from sklearn.cluster import DBSCAN
from typing import Dict, List
import pandas as pd
import logging
from openpyxl.utils.dataframe import dataframe_to_rows

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_extraction.log'),
        logging.StreamHandler()
    ]
)

# Define keys to extract and their corresponding search terms
KEY_MAPPING = {
    "Objective": "Objective",
    "Description": "Description",
    "Minimum recommended investment timeframe": "Minimum recommended",
    "Target Allocation": "Target Allocation",
    "Neutral FX Exposure": "Neutral FX Exposure",
    "Buy-sell spread": "Buy-sell Spread",
    "Inception Date": "Inception Date",
    "Base Fund Fee": "Base Fund Fee",
    "Performance Fee": "Performance Fee",
    "Total Fund Fee": "Total Fund Fee",
    "Net Asset Value": "Net Asset Value",
    "Benchmark": "Benchmark",
    "Yield": "Yield ",
    "Average Credit Rating": "Average Credit Rating",
    "Duration": "Duration"
}

# Get the keys to extract from the mapping
keys_to_extract = list(KEY_MAPPING.keys())

class KeyValuePairTextExtractor:
    """
    A hybrid PDF text extractor that first tries pdfplumber (for tables/structured data)
    and falls back to PyMuPDF (for more complex layouts) when needed.
    """
    
    def __init__(self, 
                 selection_y_tolerance: int = 11, 
                 clustering_y_tolerance: int = 2,
                 x_threshold: int = 2):
        """
        Initialize the extractor with configuration parameters.
        
        Args:
            selection_y_tolerance: Vertical tolerance for initial span selection (tighter)
            clustering_y_tolerance: Vertical tolerance for line grouping (looser)
            x_threshold: Minimum horizontal distance to consider text as a value
        """
        self.selection_y_tolerance = selection_y_tolerance
        self.clustering_y_tolerance = clustering_y_tolerance
        self.x_threshold = x_threshold
    
    def extract_with_pdfplumber(self, pdf_path: str, keys_to_extract: List[str]) -> Dict[str, str]:
        """
        Primary extraction method using pdfplumber (tables first, then words)
        Returns a dictionary with cleaned values
        """
        results = {key: "" for key in keys_to_extract}
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_page = pdf.pages[0]
                
                # First try with tables (more precise when it works)
                tables_extracted = False
                tables = first_page.extract_tables({
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "text_x_tolerance": 3,
                    "intersection_y_tolerance": 5
                })
                
                if tables:
                    for table in tables:
                        for row in table:
                            if len(row) > 1:  # Ensure row has at least 2 elements
                                for key in keys_to_extract:
                                    search_term = KEY_MAPPING[key]
                                    if search_term.lower() in str(row[0]).lower():  # Case-insensitive match
                                        value = row[-1].strip() if row[-1] else ""
                                        results[key] = value.replace('\n', ' ')
                                        tables_extracted = True
                                        break  # Move to next row after finding a match
        
        except Exception as e:
            logging.error(f"pdfplumber extraction failed for {pdf_path}: {str(e)}")
            return {key: "" for key in keys_to_extract}
        
        return results

    def extract_with_pymupdf(self, pdf_path: str, keys_to_extract: List[str]) -> Dict[str, str]:
        """
        Fallback extraction method using PyMuPDF when pdfplumber fails.
        Enhanced with specific logic for KiwiSaver fund fact sheets.
        """
        doc = fitz.open(pdf_path)
        results = {key: "" for key in keys_to_extract}
        
        try:
            for page in doc:
                blocks = page.get_text("dict")["blocks"]
                
                # First try to find "Key Fund Facts" section (specific to KiwiSaver docs)
                key_facts_found = False
                key_facts_y = 0
                
                # Find the "Key Fund Facts" section if any of our keys are typically in that section
                fund_fact_keys = {key for key in keys_to_extract if key.lower() in {
                    "objective", "description", "minimum recommended investment timeframe", 
                    "target allocation", "net asset value", "benchmark"
                }}
                
                if fund_fact_keys:
                    for b in blocks:
                        if "lines" in b:
                            for line in b["lines"]:
                                for span in line["spans"]:
                                    if "Key Fund Facts" in span["text"]:
                                        key_facts_found = True
                                        key_facts_y = span["bbox"][1]
                                        break
                                if key_facts_found:
                                    break
                            if key_facts_found:
                                break
                
                # Find all spans in the document with their positions
                all_spans = []
                for b in blocks:
                    if "lines" in b:
                        for line in b["lines"]:
                            for span in line["spans"]:
                                # If we found Key Fund Facts, only look at spans below it
                                if not key_facts_found or span["bbox"][1] >= key_facts_y:
                                    all_spans.append({
                                        "text": span["text"].strip(),
                                        "bbox": span["bbox"],
                                        "page": page.number
                                    })
                
                # Extract values for each requested key
                for key in keys_to_extract:
                    if results[key]:  # Skip if already found
                        continue
                    
                    search_term = KEY_MAPPING[key]
                    key_spans = [s for s in all_spans if s["text"].lower().startswith(search_term.lower())]
                    if not key_spans:
                        continue
                    
                    # Process each occurrence of the key
                    for key_span in key_spans:
                        key_bbox = key_span["bbox"]
                        potential_value_spans = []
                        
                        # Find spans that are aligned with the key and to its right
                        for span in all_spans:
                            if (abs(span["bbox"][1] - key_bbox[1]) <= self.selection_y_tolerance and \
                            span["bbox"][0] > key_bbox[2] + self.x_threshold):
                                potential_value_spans.append(span)
                        
                        if potential_value_spans:
                            # Cluster spans by y-coordinate to handle multi-line values
                            y_coords = np.array([[s["bbox"][1]] for s in potential_value_spans])
                            clustering = DBSCAN(eps=self.clustering_y_tolerance, min_samples=1).fit(y_coords)
                            
                            # Group and sort spans
                            clusters = {}
                            for i, span in enumerate(potential_value_spans):
                                label = clustering.labels_[i]
                                if label not in clusters:
                                    clusters[label] = []
                                clusters[label].append(span)
                            
                            # Sort each cluster by x-coordinate and combine text
                            value_lines = []
                            for cluster in clusters.values():
                                cluster.sort(key=lambda s: s["bbox"][0])
                                line_text = " ".join(s["text"] for s in cluster)
                                value_lines.append(line_text)
                            
                            value_text = " ".join(value_lines).strip()
                            if value_text:  # Only update if we found something
                                results[key] = value_text
                                break  # Move to next key after first successful extraction
                
                # Early exit if we've found all requested keys
                if all(results.values()):
                    break
        
        except Exception as e:
            logging.error(f"PyMuPDF extraction failed for {pdf_path}: {str(e)}")
            return {key: "" for key in keys_to_extract}
        
        finally:
            doc.close()
        
        return results
    
    def extract_from_pdf(self, pdf_path: str, keys_to_extract: List[str]) -> Dict[str, str]:
        """
        Combined extraction strategy:
        1. First try with pdfplumber (tables + words)
        2. For any missing fields, fall back to PyMuPDF
        """
        # First try with pdfplumber
        results = self.extract_with_pdfplumber(pdf_path, keys_to_extract)
        
        # Check if any fields are missing
        missing_fields = [key for key in keys_to_extract if not results[key]]
        
        if missing_fields:
            # Fall back to PyMuPDF for missing fields
            fallback_results = self.extract_with_pymupdf(pdf_path, missing_fields)
            
            # Update results with any successfully extracted fields
            for key, value in fallback_results.items():
                if value:
                    results[key] = value
        
        return results
    
    def extract_from_folder(self, folder_path: str, keys_to_extract: List[str]) -> Dict[str, Dict[str, str]]:
        """
        Extract specified key-value pairs from all PDFs in a folder.
        
        Args:
            folder_path: Path to the folder containing PDF files
            keys_to_extract: List of keys to extract values for
            
        Returns:
            Dictionary mapping filenames to their extracted key-value pairs
        """
        results = {}
        pdf_files = list(Path(folder_path).glob("*.pdf"))
        
        for pdf_path in pdf_files:
            try:
                logging.info(f"Processing file: {pdf_path.name}")
                extracted_data = self.extract_from_pdf(str(pdf_path), keys_to_extract)
                results[pdf_path.name] = extracted_data
            except Exception as e:
                logging.error(f"Error processing {pdf_path.name}: {str(e)}")
                results[pdf_path.name] = {key: f"Error: {str(e)}" for key in keys_to_extract}
        
        return results

def save_to_excel(results: Dict[str, Dict[str, str]], output_path: str) -> None:
    """
    Save extraction results to an Excel file with each PDF's results in a separate tab.
    
    Args:
        results: Dictionary of extraction results
        output_path: Path to save the Excel file
    """
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for filename, data in results.items():
                # First, process the filename
                parts = filename.replace("KiwiSaver", "KS").replace("Fund", "").split("_")

                # Convert full month name to short form (only if it matches a known month)
                if len(parts) >= 2:
                    month_full = parts[-2]
                    month_abbr = next((abbr for abbr, full in zip(calendar.month_abbr, calendar.month_name) if full == month_full), month_full)
                    parts[-2] = month_abbr

                # Reconstruct filename
                filename_cleaned = "".join(filter(None, parts))

                # Sanitize for Excel sheet name
                sheet_name = filename_cleaned[:31].replace(":", "").replace("\\", "").replace("/", "").replace("?", "").replace("*", "").replace("[", "").replace("]", "")
                                
                # Convert data to DataFrame
                df = pd.DataFrame(list(data.items()), columns=["Key", "Value"])
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Auto-adjust column widths
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(cell.value)
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
            
        logging.info(f"Successfully saved results to {output_path}")
    except Exception as e:
        logging.error(f"Failed to save Excel file: {str(e)}")
        raise

# Example usage
if __name__ == "__main__":
    try:
        # Initialize the extractor with default parameters
        extractor = KeyValuePairTextExtractor()
        
        # Define folder path (replace with your actual path)
        folder_path = r"C:\Users\mithu\Documents\MEGA\Projects\KiwiSaver Fund Performance & ESG Analyzer\Downloads\Milford_Asset\Kiwisaver_Monthly_Fact_Sheets\New Folder"
        
        # Extract data from all PDFs in folder
        all_results = extractor.extract_from_folder(folder_path, keys_to_extract)
        
        # Print results
        for filename, data in all_results.items():
            logging.info(f"\nResults for {filename}:")
            for key, value in data.items():
                logging.info(f"  {key}: {value if value else 'Not found'}")
        
        # Save results to Excel file
        output_path = Path(folder_path) / "extracted_results.xlsx"
        save_to_excel(all_results, str(output_path))
        
        logging.info(f"\nProcessing complete. Results saved to {output_path}")
    
    except Exception as e:
        logging.error(f"An error occurred during execution: {str(e)}", exc_info=True)
📊 KiwiSaver Fund Performance & ESG Analyzer

A modular data pipeline for scraping, extracting, and structuring KiwiSaver fund data from multiple providers (Milford, Fisher Funds, Simplicity).
This project focuses on transforming unstructured PDFs and web data into analyzable datasets.

🚀 Overview

This project solves a non-trivial problem:

Financial institutions publish fund data in PDFs, charts, and semi-structured formats — not APIs.

This pipeline:

Scrapes fund documents from multiple providers
Extracts:
📈 Performance tables
🧾 Key-value fund facts
📊 Chart data (SVG → numeric)
Cleans and normalizes the data
Exports structured datasets (Excel / DataFrames)
🧱 Architecture
                ┌──────────────────────┐
                │   Web Scrapers       │
                │ (Playwright-based)   │
                └─────────┬────────────┘
                          ↓
                ┌──────────────────────┐
                │   Raw PDFs / CSVs    │
                └─────────┬────────────┘
                          ↓
        ┌────────────────────────────────────┐
        │      PDF Parsing Layer             │
        │  - DBSCAN (layout reconstruction)  │
        │  - Camelot (table extraction)      │
        │  - pdfplumber (structured data)    │
        └─────────┬──────────────────────────┘
                  ↓
        ┌──────────────────────────────┐
        │  Data Cleaning & Normalizing │
        └─────────┬────────────────────┘
                  ↓
        ┌──────────────────────────────┐
        │ Structured Outputs (Excel/DF)│
        └──────────────────────────────┘
📦 Features
🔹 1. Web Scraping
Milford Asset Downloader
Downloads PDFs + CSVs from dynamic UI
Handles:
Tabs (KiwiSaver / Investment funds)
Shadow DOM interactions
File:
Fisher Funds Downloader
Extracts document links and downloads PDFs
Handles non-standard PDF URLs
File:
Simplicity Scraper
Filters downloads by:
Year
Month
Automatically organizes output folders
File:
🔹 2. PDF Table Extraction (Core Engine)
Numeric_Data_PDF_Parser (Advanced Version)

File:

Key capabilities:

Dual extraction strategy
DBSCAN → reconstruct tables from raw text spans (pre-2024 PDFs)
Camelot → structured extraction (2024+ PDFs)
Layout reconstruction via clustering
Row clustering (Y-axis)
Column clustering (X-axis)
Smart cleaning pipeline
Header detection
Label column detection
Row merging
% normalization
Empty column removal
Robust logging + error handling
Decorator-based exception tracing
🔹 3. Key-Value Extraction (Fund Facts)

File:

Extracts structured metadata like:

Objective
Benchmark
Fees
NAV
Duration

Approach:

Try pdfplumber (table-first strategy)
Fallback to PyMuPDF + DBSCAN clustering
🔹 4. Specialized Text Extraction

Example:

Objective + Description extraction from “Key Fund Facts”

File:

Uses:

Positional bounding boxes
Clustering for multi-line text reconstruction
🔹 5. Chart Data Extraction (Advanced)

File:

Extracts data from SVG charts
Converts pixel coordinates → actual values
Uses:
Path parsing
Linear interpolation
🔹 6. Testing

File:

Pytest-based unit tests
Covers:
DBSCAN grouping
Header detection
Data cleaning
Edge cases
⚙️ Installation
git clone <repo-url>
cd kiwisaver-analyzer

pip install -r requirements.txt
playwright install
▶️ Usage
1. Download Data
from Milford_Asset_Numeric_Tables import MilfordAssetScraper

scraper = MilfordAssetScraper(headless=True)
scraper.run()
2. Extract Performance Tables
from Fisher_Funds_Numeric_Tables import Numeric_Data_PDF_Parser

parser = Numeric_Data_PDF_Parser(
    folder_path="path/to/pdfs",
    terms_to_search=["Investment Performance after fees as at"]
)

parser.validate_and_export()
3. Extract Fund Facts
from MilfordAsset_Key_Value_Pairs import KeyValuePairTextExtractor

extractor = KeyValuePairTextExtractor()
data = extractor.extract_from_pdf("fund.pdf", keys_to_extract)
📊 Output
Excel files (multi-sheet)
Clean tabular data
Key-value structured metadata
Time series datasets (from charts)
🧠 Key Techniques Used
DBSCAN clustering (layout reconstruction)
PDF parsing (PyMuPDF, pdfplumber, Camelot)
Playwright automation
SVG parsing + interpolation
Heuristic-based data cleaning
⚠️ Challenges Solved
Inconsistent PDF layouts across years
Multi-line cell reconstruction
Missing table boundaries
Non-tabular structured text
Chart data extraction from SVG paths
🔮 Roadmap
 ESG data extraction
 Unified schema across providers
 Database integration (PostgreSQL / DuckDB)
 Dashboard (Power BI / Streamlit)
 Automated pipeline scheduling
🤝 Contributing

Contributions are welcome — especially for:

New fund providers
Better table extraction heuristics
Performance optimizations
📄 License

MIT License (or your choice)

👤 Author

Mithun M. Thakkar
AI Engineer | Financial Data Specialist

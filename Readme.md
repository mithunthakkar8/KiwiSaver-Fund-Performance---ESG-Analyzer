# 📊 KiwiSaver Fund Performance & ESG Analyzer

A modular data pipeline for scraping, extracting, and structuring KiwiSaver fund data from multiple providers (Milford, Fisher Funds, Simplicity).

This project focuses on transforming unstructured PDFs and web data into analyzable datasets.

---

## 🚀 Overview

This project solves a non-trivial problem:

> Financial institutions publish fund data in PDFs, charts, and semi-structured formats — not APIs.

### This pipeline:
- 📥 Scrapes fund documents from multiple providers  
- 📊 Extracts:
  - Performance tables  
  - Key-value fund facts  
  - Chart data (SVG → numeric)  
- 🧹 Cleans and normalizes the data  
- 📤 Exports structured datasets (Excel / DataFrames)

---

## 🧱 Architecture

```text
Web Scrapers (Playwright)
        ↓
Raw PDFs / CSVs
        ↓
PDF Parsing Layer
  - DBSCAN (layout reconstruction)
  - Camelot (table extraction)
  - pdfplumber (structured data)
        ↓
Data Cleaning & Normalization
        ↓
Structured Outputs (Excel / DataFrames)
```

## 📦 Features

### 🔹 1. Web Scraping

**Milford Asset Downloader**
- Downloads PDFs + CSVs from dynamic UI
- Handles tabs (KiwiSaver / Investment funds)
- Handles Shadow DOM interactions

**Fisher Funds Downloader**
- Extracts document links and downloads PDFs
- Handles non-standard PDF URLs

**Simplicity Scraper**
- Filters downloads by year and month
- Automatically organizes output folders

---

### 🔹 2. PDF Table Extraction (Core Engine)

**Numeric_Data_PDF_Parser**

- DBSCAN → layout reconstruction for messy PDFs  
- Camelot → structured table extraction  
- pdfplumber → structured data fallback  

**Data Cleaning Capabilities**
- Header detection  
- Label column detection  
- Row merging  
- Percentage normalization  
- Empty column removal  

---

### 🔹 3. Key-Value Extraction

- Extracts:
  - Objective  
  - Benchmark  
  - Fees  
  - Net Asset Value (NAV)  

**Approach**
- pdfplumber (tables first)  
- PyMuPDF fallback  

---

### 🔹 4. Chart Data Extraction

- Extracts data from SVG charts  
- Converts pixel coordinates → numeric values  
- Uses interpolation for accuracy  

---

### 🔹 5. Testing

- Pytest-based unit tests  
- Covers:
  - DBSCAN grouping  
  - Header detection  
  - Data cleaning  
  - Edge cases  

---

## ⚙️ Installation

```bash
git clone <your-repo-url>
cd kiwisaver-analyzer

pip install -r requirements.txt
playwright install
```

## ▶️ Usage

### 1. Download Data

```python
from Milford_Asset_Numeric_Tables import MilfordAssetScraper

scraper = MilfordAssetScraper(headless=True)
scraper.run()
```

2. Extract Performance Tables
```python
from Fisher_Funds_Numeric_Tables import Numeric_Data_PDF_Parser

parser = Numeric_Data_PDF_Parser(
    folder_path="path/to/pdfs",
    terms_to_search=["Investment Performance after fees as at"]
)

parser.validate_and_export()
```

3. Extract Fund Facts
```python
from MilfordAsset_Key_Value_Pairs import KeyValuePairTextExtractor

keys_to_extract = [
    "Objective",
    "Benchmark",
    "Base Fund Fee",
    "Net Asset Value"
]

extractor = KeyValuePairTextExtractor()
data = extractor.extract_from_pdf("fund.pdf", keys_to_extract)
```

📊 Output
Excel files (multi-sheet)
Clean tabular datasets
Key-value structured metadata
Time series datasets (from charts)

🧠 Key Techniques
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
Extracting data from charts

🔮 Roadmap
 ESG data extraction
 Unified schema across providers
 Database integration (PostgreSQL / DuckDB)
 Dashboard (Power BI / Streamlit)
 Automated scheduling
👤 Author

Mithun M. Thakkar
AI Engineer | Financial Data Specialist

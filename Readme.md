KiwiSaver Fund Performance & ESG Analyzer
A comprehensive toolkit for scraping, parsing, and analyzing KiwiSaver fund data from major New Zealand providers including Milford Asset Management, Fisher Funds, and Simplicity.

📋 Overview
This project automates the extraction and analysis of KiwiSaver fund information from PDF fact sheets and web dashboards. It handles:

PDF scraping from provider websites

Intelligent parsing of semi-structured PDF documents

Data extraction for performance metrics, fund facts, and ESG indicators

Structured output to Excel and CSV formats

🏗️ Project Structure
text
KiwiSaver Fund Performance & ESG Analyzer/
├── scrapers/                          # Web scraping modules
│   ├── Milford_Fund_Report_Downloader.py
│   ├── Fisher_Funds_Scraper.py
│   └── Simplicity_Documents_Scraper.py
├── parsers/                           # PDF parsing modules
│   ├── Fisher_Funds_Numeric_Tables.py
│   ├── Milford_Asset_Numeric_Tables.py
│   ├── MilfordAsset_Key_Value_Pairs.py
│   └── extract_fund_facts.py
├── scrapers/                          # Web scraping utilities
│   ├── Fisher_Funds_Performance_Scraper.py
│   ├── Milford_Performance_Scraper.py
│   └── User Agent Info.py
└── tests/                             # Unit tests
    └── test_Fisher_Funds.py
🚀 Features
PDF Scraping
Playwright-based automation for dynamic JavaScript-rendered content

Smart filtering by month/year for selective downloads

Headless/visible mode support for debugging

PDF Parsing
Dual-parser strategy: Uses both PyMuPDF (fitz) and Camelot

Year-based parser selection: Camelot for 2024+ PDFs (table-friendly), DBSCAN clustering for older formats

Key-value extraction for fund facts (Objective, Description, Fees, Asset Allocation)

Top 10 investments table extraction

Data Processing
DBSCAN clustering for row/column detection in unstructured PDFs

Intelligent header detection and table normalization

Automatic Excel export with formatted sheets

📦 Dependencies
bash
pip install pymupdf          # PDF text extraction
pip install camelot-py       # Table extraction (CV2-based)
pip install pandas           # Data manipulation
pip install numpy            # Numerical operations
pip install scikit-learn     # DBSCAN clustering
pip install playwright       # Web scraping
pip install openpyxl         # Excel export
pip install pdfplumber       # Alternative PDF parser
After installing Playwright, install browser binaries:

bash
playwright install chromium
🔧 Usage Examples
1. Download Fact Sheets
python
from Milford_Fund_Report_Downloader import Fund_Report_Downloader
from playwright.sync_api import sync_playwright

download_configs = [{
    "url": "https://milfordasset.com/documents/kiwisaver-funds-monthly-fact-sheets",
    "folder": "Kiwisaver_Monthly_Fact_Sheets",
    "button_selector": 'a.gcd-btn[role="button"]:has-text("Download PDF")',
    "months": ["March", "June", "September", "December"],
    "years": [2024, 2025]
}]

with sync_playwright() as playwright:
    downloader = Fund_Report_Downloader(headless=False)
    downloader.download_all(playwright, download_configs)
2. Extract Numeric Tables
python
from Fisher_Funds_Numeric_Tables import Numeric_Data_PDF_Parser

parser = Numeric_Data_PDF_Parser(
    folder_path="path/to/pdfs",
    terms_to_search=["Top 10 investments"],
    validation_file="Top_10_investments.xlsx",
    x_tolerance=10,
    y_tolerance=10
)
parser.validate_and_export()
3. Extract Key-Value Fund Facts
python
from MilfordAsset_Key_Value_Pairs import KeyValuePairTextExtractor

extractor = KeyValuePairTextExtractor()
results = extractor.extract_from_folder(
    folder_path="path/to/pdfs",
    keys_to_extract=["Objective", "Description", "Total Fund Fee", "Net Asset Value"]
)
save_to_excel(results, "fund_facts.xlsx")
4. Extract Fund Objective & Description
python
from extract_fund_facts import extract_fund_facts

data = extract_fund_facts("KiwiSaver_Active_Growth_Fund_April_2025.pdf")
print(f"Objective: {data['objective']}")
print(f"Description: {data['description']}")
⚙️ Configuration Parameters
Parameter	Description	Default
x_tolerance	Horizontal tolerance for column detection (pixels)	10-20
y_tolerance	Vertical tolerance for row detection (pixels)	8-10
data_area_height	Height of data area below search term	160-600
data_area_width	Width of data area from search term	255-595
🧠 Parsing Strategy
Camelot (2024+ PDFs)
Better for tables with explicit borders

Uses stream flavor for borderless tables

DBSCAN (Pre-2024 PDFs)
Clusters text spans by Y-coordinate for rows

Clusters by X-coordinate for columns

Filters out footers and non-data text

📊 Output Format
Key-Value extraction: Excel with each PDF as separate sheet (Key/Value columns)

Numeric tables: Excel with preserved table structure

Fund facts: Dictionary or Excel with structured data

🧪 Testing
Run unit tests:

bash
pytest tests/test_Fisher_Funds.py -v
Test coverage includes:

PDF parsing initialization

DBSCAN grouping logic

Table cleaning and normalization

Year extraction from filenames

⚠️ Known Limitations
PDF format variations: Each provider uses different layouts

Table detection: May fail with complex multi-line cells

Year parsing: Requires 4-digit year in filename for method selection

Playwright selectors: May break if website structure changes

🔄 Future Improvements
Add support for more providers (Generate, Booster, etc.)

Integrate ESG scoring from extracted holdings

Add command-line interface (CLI)

Implement parallel PDF processing

Add visualization module for performance trends

📝 Logging
All modules include comprehensive logging:

Console output for real-time monitoring

File output (pdf_parser.log, scraper.log, etc.) for debugging

🤝 Contributing
Fork the repository

Create a feature branch

Add tests for new functionality

Submit a pull request

📄 License
MIT License - see LICENSE file for details

🙏 Acknowledgements
PyMuPDF - PDF processing

Camelot - Table extraction

Playwright - Browser automation

scikit-learn - DBSCAN clustering

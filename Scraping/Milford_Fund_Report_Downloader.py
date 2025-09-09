import requests
import random
import time
from datetime import datetime
from playwright.sync_api import Playwright, sync_playwright
import logging
from pathlib import Path
from typing import Dict, List

class Fund_Report_Downloader:
    def __init__(self, headless=True, base_dir="downloads/Milford_Asset", min_delay=1, max_delay=3):
        self.headless = headless
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.min_delay = min_delay
        self.max_delay = max_delay
        
        # Set up logging to both console and file
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging to both console and file"""
        # Clear any existing handlers
        logging.getLogger().handlers.clear()
        
        # Create log directory if it doesn't exist
        log_dir = self.base_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Create a timestamped log filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"download_{timestamp}.log"
        
        # Set up logging configuration
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),  # Log to file
                logging.StreamHandler()        # Log to console
            ]
        )
        self.logger = logging.getLogger()
        self.logger.info(f"Logging initialized. Log file: {log_file}")

    def download_all(self, playwright: Playwright, download_configs: List[Dict]):
        """Process all download configurations with month/year filtering"""
        self.logger.info("Starting download process")
        
        for config in download_configs:
            try:
                folder_path = self.base_dir / config['folder']
                folder_path.mkdir(parents=True, exist_ok=True)
                
                self.logger.info(f"Processing {config['url']} -> {folder_path}")
                
                months = config.get('months', [])
                years = config.get('years', [])
                
                self.download_files_with_filters(
                    playwright,
                    config['url'],
                    folder_path,
                    config['button_selector'],
                    months,
                    years
                )
                    
            except Exception as e:
                self.logger.error(f"Failed to process {config.get('url', 'unknown')}: {e}")
        
        self.logger.info("Download process completed")

    def download_files_with_filters(self, playwright: Playwright, url: str, save_path: Path, 
                                 selector: str, months: List[str], years: List[int]):
        """Download files from page using the selector with month/year filters"""
        browser = playwright.chromium.launch(headless=self.headless)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            self.logger.info(f"Navigating to {url}")
            page.goto(url)
            
            rows = page.locator('tbody tr')
            row_count = rows.count()
            self.logger.info(f"Found {row_count} rows in the table")

            for i in range(row_count):
                row = rows.nth(i)
                try:
                    date_str = row.locator('td:nth-child(1)').inner_text()
                    fund_name = row.locator('.fund-name').inner_text()
                    download_button = row.locator(selector)
                    
                    month_name = None
                    year = None
                    
                    try:
                        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                        month_name = date_obj.strftime('%B')
                        year = date_obj.year
                    except ValueError:
                        try:
                            year = int(date_str)
                            month_name = "Annual"
                        except ValueError:
                            self.logger.warning(f"Could not parse date: {date_str}")
                            continue
                    
                    if months and month_name != "Annual" and month_name not in months:
                        self.logger.debug(f"Skipping {fund_name} - {month_name if month_name else 'Annual'} {year} (month filter)")
                        continue
                    if years and year not in years:
                        self.logger.debug(f"Skipping {fund_name} - {month_name if month_name else 'Annual'} {year} (year filter)")
                        continue
                    
                    if month_name and month_name != "Annual":
                        filename = f"{fund_name.replace(' ', '_')}_{month_name}_{year}.pdf"
                    else:
                        filename = f"{fund_name.replace(' ', '_')}_Annual_{year}.pdf"
                    
                    full_path = save_path / filename
                    
                    if full_path.exists():
                        self.logger.info(f"File already exists, skipping: {filename}")
                        continue
                        
                    self._download_pdf_file(page, download_button, save_path, filename)
                    
                    delay = random.uniform(self.min_delay, self.max_delay)
                    self.logger.info(f"Waiting {delay:.2f} seconds before next download...")
                    time.sleep(delay)
                    
                except Exception as e:
                    self.logger.error(f"Processing failed at row {i}: {e}")
        finally:
            context.close()
            browser.close()

    def _download_pdf_file(self, page, handle, save_path: Path, filename: str):
        """Handle actual file download with specified filename"""
        try:
            if self.headless:
                with page.expect_download() as download_info:
                    handle.click()
                download = download_info.value
                full_path = save_path / filename
                download.save_as(full_path)
            else:
                with page.context.expect_page() as new_tab_info:
                    handle.click()
                new_tab = new_tab_info.value
                new_tab.wait_for_load_state()
                pdf_url = new_tab.url
                new_tab.close()

                response = requests.get(pdf_url)
                full_path = save_path / filename
                with open(full_path, "wb") as f:
                    f.write(response.content)

            self.logger.info(f"Saved: {full_path}")
        except Exception as e:
            self.logger.error(f"Error downloading PDF: {str(e)}")


if __name__ == "__main__":
    # Configuration for multiple URLs and folders with month/year filters
    download_configs = [
        {
            "url": "https://milfordasset.com/documents/investment-funds-annual-reports",
            "folder": "IF_Annual_Updates",
            "button_selector": 'a.gcd-btn[role="button"]:has-text("Download PDF")',
            "months": [],  # Only download March and December reports
            "years": []             # Only download for 2023 and 2024
        }
        ,
        {
            "url": "https://milfordasset.com/documents/kiwisaver-funds-monthly-fact-sheets",
            "folder": "Kiwisaver_Monthly_Fact_Sheets",
            "button_selector": 'a.gcd-btn[role="button"]:has-text("Download PDF")',
            "months": [],  # Only download March and December reports
            "years": []             # Only download for 2023 and 2024
        }
        ,
        {
            "url": "https://milfordasset.com/documents/milford-monthly-fund-overview",
            "folder": "Fund_Overviews",
            "button_selector": 'a.gcd-btn[role="button"]:has-text("Download PDF")',
            "months": [],  # Only download March and December reports
            "years": []             # Only download for 2023 and 2024
        }
        ,
        {
            "url": "https://milfordasset.com/documents/investment-funds-monthly-fact-sheets",
            "folder": "Investment_Funds_Fact_Sheets",
            "button_selector": 'a.gcd-btn[role="button"]:has-text("Download PDF")',
            "months": [],  # Only download March and December reports
            "years": []             # Only download for 2023 and 2024
        }
        ,
        {
            "url": "https://milfordasset.com/documents/kiwisaver-funds-quarterly-fund-updates",
            "folder": "KS_Quarterly_Updates",
            "button_selector": 'a.gcd-btn[role="button"]:has-text("Download PDF")',
            "months": [],  # Only download March and December reports
            "years": []             # Only download for 2023 and 2024
        }
        ,
        {
            "url": "https://milfordasset.com/documents/investment-funds-quarterly-fund-updates",
            "folder": "IF_Quarterly_Updates",
            "button_selector": 'a.gcd-btn[role="button"]:has-text("Download PDF")',
            "months": [],  # Only download March and December reports
            "years": []             # Only download for 2023 and 2024
        }
        ,
        {
            "url": "https://milfordasset.com/documents/kiwisaver-funds-annual-reports",
            "folder": "KS_Annual_Updates",
            "button_selector": 'a.gcd-btn[role="button"]:has-text("Download PDF")',
            "months": [],  # Only download March and December reports
            "years": []             # Only download for 2023 and 2024
        }
        

    ]

    with sync_playwright() as playwright:
        downloader = Fund_Report_Downloader(
            headless=False,  # Set True for headless
            min_delay=1,
            max_delay=3
        )
        downloader.download_all(playwright, download_configs)


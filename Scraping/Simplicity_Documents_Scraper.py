import os
import logging
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

class SimplicityScraper:
    def __init__(self, year_filter=None, month_filter=None):
        self.base_dir = os.path.join(os.getcwd(), "Downloads", "Simplicity")
        self.kiwisaver_dir = os.path.join(self.base_dir, "KiwiSaver")
        self.investment_dir = os.path.join(self.base_dir, "InvestmentFunds")
        self.log_file = os.path.join(self.base_dir, "scraper.log")
        self.year_filter = year_filter
        self.month_filter = month_filter
        
        os.makedirs(self.kiwisaver_dir, exist_ok=True)
        os.makedirs(self.investment_dir, exist_ok=True)
        
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _should_download(self, date_str):
        try:
            doc_date = datetime.strptime(date_str, "%d %B %Y")
            
            if self.year_filter and doc_date.year != self.year_filter:
                return False
            if self.month_filter and doc_date.month != self.month_filter:
                return False
            return True
        except ValueError:
            self.logger.warning(f"Could not parse date: {date_str}")
            return True

    def _file_exists(self, output_dir, filename):
        filepath = os.path.join(output_dir, filename)
        return os.path.exists(filepath)

    def scrape_documents(self, page, url, output_dir):
        try:
            page.goto(url, timeout=0)
            self.logger.info(f"Scraping: {url}")

            page.wait_for_selector(".document-item", timeout=0)
            documents = page.query_selector_all(".document-item")
            self.logger.info(f"Found {len(documents)} documents")

            for doc in documents:
                try:
                    title = doc.query_selector(".document-title").inner_text().strip()
                    date = doc.query_selector(".document-date").inner_text().strip()
                    download_url = doc.query_selector(".document-download").get_attribute("href")

                    if not self._should_download(date):
                        self.logger.info(f"Skipping {title} (date filter)")
                        continue

                    clean_title = "".join(c if c.isalnum() or c in (' ', '-') else '_' for c in title)
                    filename = f"{date.replace(' ', '_')}_{clean_title}.pdf"

                    if self._file_exists(output_dir, filename):
                        self.logger.info(f"Already exists: {filename}")
                        continue

                    with page.expect_download() as download_info:
                        page.evaluate(f"""() => {{
                            const anchor = document.createElement('a');
                            anchor.href = '{download_url}';
                            anchor.download = '';
                            document.body.appendChild(anchor);
                            anchor.click();
                            document.body.removeChild(anchor);
                        }}""")
                    
                    download = download_info.value
                    download.save_as(os.path.join(output_dir, filename))
                    self.logger.info(f"Downloaded: {filename}")

                except Exception as e:
                    self.logger.error(f"Failed to process document: {title} - {str(e)}")

        except Exception as e:
            self.logger.error(f"Error scraping {url}: {str(e)}")

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.context.set_default_timeout(60000)

            try:
                self.scrape_documents(
                    page,
                    "https://simplicity.kiwi/kiwisaver/documents",
                    self.kiwisaver_dir
                )

                self.scrape_documents(
                    page,
                    "https://simplicity.kiwi/investment-funds/documents",
                    self.investment_dir
                )

            finally:
                browser.close()

        self.logger.info("\nScraping completed!")
        self.logger.info(f"KiwiSaver documents: {self.kiwisaver_dir}")
        self.logger.info(f"Investment documents: {self.investment_dir}")
        self.logger.info(f"Log file: {self.log_file}")

if __name__ == "__main__":
    # Example: Only download documents from March 2025
    scraper = SimplicityScraper(year_filter=2017)
    scraper.run()
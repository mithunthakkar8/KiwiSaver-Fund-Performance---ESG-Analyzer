import os
import re
import requests
import shutil
import logging
import unittest
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MilfordAssetScraper:
    def __init__(self, headless=False):
        self.headless = headless
        self.base_dir = os.path.join(os.getcwd(), "Downloads", "Milford_Asset")
        self.pdf_dir = os.path.join(self.base_dir, "PDF")
        self.csv_dir = os.path.join(self.base_dir, "CSV")
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.pdf_dir, exist_ok=True)
        os.makedirs(self.csv_dir, exist_ok=True)

    @staticmethod
    def _get_filename_from_response(response, url):
        cd = response.headers.get("Content-Disposition")
        if cd:
            match = re.findall('filename="?([^\"]+)"?', cd)
            if match:
                return match[0]
        return url.split("/")[-1].split("?")[0]        

    def _switch_tab(self, page, tab_name):
        """Switch to specified tab and verify the switch was successful"""
        tab_locator = page.locator(f"ul.nav-tabs li.nav-item:has(a:has-text('{tab_name} Funds'))")

        if tab_locator.locator("a").get_attribute("aria-selected") == "true":
            logger.info(f"{tab_name} tab is already active")
            return True

        logger.info(f"Switching to {tab_name} tab...")
        tab_locator.click()

        try:
            page.wait_for_selector(
                f"ul.nav-tabs li.nav-item a[aria-selected='true']:has-text('{tab_name} Funds')",
                timeout=10000
            )
            logger.info(f"Successfully switched to {tab_name} tab")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to {tab_name} tab: {str(e)}")
            return False

    def download_pdfs(self, page, tab_name):
        logger.info(f"\nStarting PDF downloads for {tab_name}...")

        if not hasattr(self, '_initial_pdf_downloaded'):
            self._initial_pdf_downloaded = False

        if not self._initial_pdf_downloaded:
            try:
                logger.info("\nProcessing INITIAL/ALL-FUNDS download button...")
                all_funds = page.locator("all-funds")
                if all_funds.count() > 0:
                    all_funds.first.evaluate("""
                        el => {
                            const shadow = el.shadowRoot;
                            const img = shadow.querySelector('img[alt="download"]');
                            if (img) img.click();
                        }
                    """)

                    page.wait_for_selector(".popover a", state="visible", timeout=5000)
                    links = page.locator(".popover a").element_handles()

                    for handle in links:
                        text = handle.text_content().lower().strip()
                        if "pdf" in text:
                            self._download_pdf_file(page, handle)

                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                    self._initial_pdf_downloaded = True
            except Exception as e:
                logger.error(f"Error processing initial download: {str(e)}")
                page.keyboard.press("Escape")

        logger.info("\nProcessing INDIVIDUAL fund download buttons...")

        try:
            download_icons = page.locator("div.fund-grid img[alt='download']:visible")
            total_icons = download_icons.count()
            logger.info(f"Found {total_icons} fund download icons")

            for i in range(total_icons):
                try:
                    logger.info(f"Processing fund {i+1}/{total_icons}")
                    icon = download_icons.nth(i)
                    icon.scroll_into_view_if_needed()
                    icon.click()

                    page.wait_for_selector(".popover a", state="visible", timeout=3000)
                    links = page.locator(".popover a").all()

                    for handle in links:
                        href = handle.get_attribute("href")
                        if href:
                            self._download_pdf_file(page, handle)

                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                except Exception as e:
                    logger.warning(f"Error processing fund {i+1}: {str(e)}")
                    page.keyboard.press("Escape")
        except Exception as e:
            logger.error(f"Error processing fund grid: {str(e)}")

    def _download_pdf_file(self, page, handle):
        """Helper method to handle actual file download"""
        try:
            if self.headless:
                with page.expect_download() as download_info:
                    handle.click()
                download = download_info.value
                filename = download.suggested_filename
                save_path = os.path.join(self.pdf_dir, filename)
                download.save_as(save_path)
            else:
                with page.context.expect_page() as new_tab_info:
                    handle.click()
                new_tab = new_tab_info.value
                new_tab.wait_for_load_state()
                pdf_url = new_tab.url
                new_tab.close()

                response = requests.get(pdf_url)
                filename = self._get_filename_from_response(response, pdf_url)
                file_path = os.path.join(self.pdf_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(response.content)
            logger.info(f"  Saved: {filename}")
        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")

    def download_csvs(self, page):
        logger.info("\nStarting CSV downloads...")

        if not hasattr(self, '_initial_csv_downloaded'):
            self._initial_csv_downloaded = False

        if not self._initial_csv_downloaded:
            try:
                all_funds = page.locator("all-funds")
                if all_funds.count() > 0:
                    logger.info("Attempting to download all-funds CSV...")
                    all_funds.first.evaluate("""
                        el => {
                            const shadow = el.shadowRoot;
                            const img = shadow.querySelector('img[alt="download"]');
                            if (img) img.click();
                        }
                    """)

                    with page.expect_download() as download_info:
                        all_funds.first.evaluate("""
                            el => {
                                const shadow = el.shadowRoot;
                                const csvLink = Array.from(shadow.querySelectorAll('a'))
                                    .find(a => a.textContent.trim().includes("CSV"));
                                if (csvLink) csvLink.click();
                            }
                        """)

                    download = download_info.value
                    file_path = os.path.join(self.csv_dir, download.suggested_filename)
                    download.save_as(file_path)
                    logger.info(f"Initial all-funds CSV downloaded: {file_path}")
                    self._initial_csv_downloaded = True
            except Exception as e:
                logger.warning(f"Could not download initial CSV: {str(e)[:200]}")

        try:
            download_icons = page.locator("div.fund-grid img[alt='download']:visible")
            total_icons = download_icons.count()
            logger.info(f"Found {total_icons} fund download icons")

            for i in range(total_icons):
                try:
                    logger.info(f"Processing fund {i+1}/{total_icons}")
                    icon = download_icons.nth(i)
                    icon.scroll_into_view_if_needed()
                    icon.click()

                    page.wait_for_selector("app-download-options", state="visible", timeout=5000)
                    download_options = page.locator("app-download-options").last

                    with page.expect_download() as download_info:
                        download_options.evaluate("""
                            el => {
                                const shadow = el.shadowRoot;
                                const link = [...shadow.querySelectorAll('p.download-link')]
                                    .find(e => e.textContent.trim() === 'Download Unit Price History');
                                if (link) link.click();
                            }
                        """)

                    download = download_info.value
                    file_path = os.path.join(self.csv_dir, download.suggested_filename)
                    download.save_as(file_path)
                    logger.info(f"Downloaded: {file_path}")

                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                except Exception as e:
                    logger.warning(f"Error processing fund {i+1}: {str(e)}")
                    page.keyboard.press("Escape")
        except Exception as e:
            logger.error(f"Error processing fund grid: {str(e)}")

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                accept_downloads=True,
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()

            # Navigate to performance page
            page.goto("https://milfordasset.com/funds-performance/view-performance", wait_until='domcontentloaded', timeout=120000)
            page.wait_for_selector("ul.nav-tabs", state="visible")

            for tab_name in ["Investment", "KiwiSaver"]:
                logger.info(f"\n{'='*40}\nProcessing {tab_name} Funds\n{'='*40}")

                if not self._switch_tab(page, tab_name):
                    continue

                self.download_pdfs(page, tab_name)
                self.download_csvs(page)

            browser.close()

    def reorganize_downloads_by_suffix(self):
        """
        Reorganize downloads by moving PDF and CSV folders into a new folder
        named after a 5-character suffix found in PDF filenames.
        """
        suffix = None
        for filename in os.listdir(self.pdf_dir):
            parts = os.path.splitext(filename)[0].split('_')
            if len(parts) > 1 and len(parts[-1]) == 5:
                suffix = parts[-1]
                break

        if not suffix:
            logger.warning("No suitable 5-character suffix found in PDF filenames")
            return

        target_dir = os.path.join(self.base_dir, 'Recent', suffix)
        os.makedirs(target_dir, exist_ok=True)

        try:
            pdf_target = os.path.join(target_dir, "PDF")
            shutil.move(self.pdf_dir, pdf_target)
            self.pdf_dir = pdf_target

            csv_target = os.path.join(target_dir, "CSV")
            shutil.move(self.csv_dir, csv_target)
            self.csv_dir = csv_target

            logger.info(f"Moved download folders to: {target_dir}")
        except Exception as e:
            logger.error(f"Error moving directories: {str(e)}")
            if os.path.exists(pdf_target) and not os.path.exists(csv_target):
                shutil.move(pdf_target, self.pdf_dir)

# Unit testing boilerplate
class TestMilfordAssetScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = MilfordAssetScraper()

    def test_directory_creation(self):
        self.assertTrue(os.path.exists(self.scraper.pdf_dir))
        self.assertTrue(os.path.exists(self.scraper.csv_dir))

if __name__ == "__main__":
    scraper = MilfordAssetScraper(headless=True)
    scraper.run()
    scraper.reorganize_downloads_by_suffix()
    # To run tests: uncomment next line
    # unittest.main()

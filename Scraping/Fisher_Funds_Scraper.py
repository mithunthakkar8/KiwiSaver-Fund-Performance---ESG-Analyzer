import os
import requests
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

class FisherFundsDownloader:
    def __init__(self, base_download_dir='downloads/Fisher_Funds'):
        self.base_download_dir = base_download_dir
        os.makedirs(self.base_download_dir, exist_ok=True)

    def _get_category_folder(self, url):
        # Extract category folder from URL path (e.g., kiwisaver, managed-funds)
        path_parts = urlparse(url).path.strip('/').split('/')
        # Example: ['kiwisaver', 'forms-and-documents']
        if len(path_parts) > 0:
            return path_parts[0]
        return 'unknown_category'

    def _get_pdf_links(self, page):
        # Extract all PDF URLs and their titles from the page
        links = []
        # Locate document items container
        doc_items = page.query_selector_all('div.documents-list div.document-item')
        for item in doc_items:
            title_el = item.query_selector('span.document-item__title')
            link_el = item.query_selector('a.link[href]')
            if title_el and link_el:
                title = title_el.inner_text().strip()
                href = link_el.get_attribute('href')
                # Only take PDF links or assets with URLs that look like PDFs
                if href and href.lower().endswith('.pdf'):
                    links.append((title, href))
                else:
                    # Some URLs don't end with .pdf but are still PDFs (like the example)
                    # We try to fetch headers later or just assume all are PDFs here
                    links.append((title, href))
        return links

    def _sanitize_filename(self, name):
        # Simple sanitizer for filenames
        return "".join(c for c in name if c.isalnum() or c in " .-_()").rstrip()

    def _download_pdf(self, url, filepath):
        # Download PDF via requests only if not exists
        if os.path.exists(filepath):
            print(f"[SKIP] Already exists: {filepath}")
            return
        print(f"[DOWNLOAD] {url} -> {filepath}")
        response = requests.get(url)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            f.write(response.content)

    def download_from_url(self, url):
        category = self._get_category_folder(url)
        target_folder = os.path.join(self.base_download_dir, category)
        os.makedirs(target_folder, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url)
            # Wait for the document list to load - adjust if needed
            page.wait_for_selector('div.documents-list')

            pdf_links = self._get_pdf_links(page)
            if not pdf_links:
                print("No PDF links found.")
                browser.close()
                return

            for title, link in pdf_links:
                filename = self._sanitize_filename(title) + '.pdf'
                filepath = os.path.join(target_folder, filename)
                self._download_pdf(link, filepath)

            browser.close()


if __name__ == '__main__':
    downloader = FisherFundsDownloader()

    urls = [
        "https://fisherfunds.co.nz/kiwisaver/forms-and-documents?productId=kiwisaver&documentType=Quarterly+Fund+Updates",
        "https://fisherfunds.co.nz/managed-funds/forms-and-documents"
    ]

    for url in urls:
        print(f"\nScraping PDFs from: {url}")
        downloader.download_from_url(url)

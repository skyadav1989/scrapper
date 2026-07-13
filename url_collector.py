import os
import re
import csv
import logging
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Constants
BASE_URL = "https://havells.com/all-products"
BATCH_SIZE = 10        # Number of pages to fetch in parallel per batch
MAX_PAGES = 200        # Safety cap to prevent infinite loops

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
TIMEOUT_SECONDS = 20


def normalize_product_url(raw_url):
    """
    Cleans a product URL:
      - Strips query parameters and fragments (e.g. ?chimney_size_variant=9472)
      - Fixes double slashes in the path (e.g. havells.com//product -> havells.com/product)
    Returns the clean URL string, or None if invalid.
    """
    try:
        parsed = urlparse(raw_url)
        if parsed.scheme not in ("http", "https"):
            return None

        # Clean duplicate slashes in path
        clean_path = re.sub(r"/{2,}", "/", parsed.path)
        if not clean_path.startswith("/"):
            clean_path = "/" + clean_path

        return f"{parsed.scheme}://{parsed.netloc}{clean_path}"
    except Exception:
        return None


def fetch_product_urls_from_page(page_num):
    """
    Fetches a single paginated page and extracts product detail URLs
    from <a class="product-item-link"> elements.
    Returns a tuple: (page_num, set_of_normalized_urls)
    """
    url = BASE_URL if page_num == 1 else f"{BASE_URL}?p={page_num}"
    product_urls = set()
    try:
        logging.info("Fetching page %d: %s", page_num, url)
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        if r.status_code != 200:
            logging.warning("Page %d returned status %d", page_num, r.status_code)
            return (page_num, product_urls)

        soup = BeautifulSoup(r.text, "lxml")
        for a_tag in soup.select("a.product-item-link"):
            href = a_tag.get("href")
            if not href:
                continue
            normalized = normalize_product_url(href)
            if normalized:
                product_urls.add(normalized)

    except requests.exceptions.RequestException as e:
        logging.warning("Request error on page %d: %s", page_num, e)
    except Exception as e:
        logging.error("Unexpected error on page %d: %s", page_num, e)

    return (page_num, product_urls)


def collect_all_product_urls():
    """
    Crawls all paginated pages of the all-products catalog in parallel batches.
    Stops when a batch contains a page with 0 products.
    """
    all_product_urls = set()
    current_start = 1

    while current_start <= MAX_PAGES:
        batch_end = min(current_start + BATCH_SIZE, MAX_PAGES + 1)
        page_numbers = list(range(current_start, batch_end))

        logging.info("--- Fetching batch: pages %d to %d ---", page_numbers[0], page_numbers[-1])

        stop_after_batch = False

        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
            futures = {
                executor.submit(fetch_product_urls_from_page, p): p
                for p in page_numbers
            }

            for future in as_completed(futures):
                page_num, urls = future.result()
                if len(urls) == 0:
                    logging.info("Page %d returned 0 products. Will stop after this batch.", page_num)
                    stop_after_batch = True
                else:
                    before = len(all_product_urls)
                    all_product_urls.update(urls)
                    new_count = len(all_product_urls) - before
                    logging.info("Page %d: found %d product links (%d new)", page_num, len(urls), new_count)

        logging.info("Batch complete. Total unique product URLs so far: %d", len(all_product_urls))

        if stop_after_batch:
            logging.info("Stopping: encountered a page with no products.")
            break

        current_start = batch_end

    # Save the output
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "havells_products.csv")

    logging.info("Saving %d unique product URLs to %s", len(all_product_urls), output_file)
    try:
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["product_url"])
            for url in sorted(all_product_urls):
                writer.writerow([url])
    except PermissionError:
        import time
        fallback = os.path.join(output_dir, f"havells_products_{int(time.time())}.csv")
        logging.warning("Permission denied on '%s'. Saving to '%s'", output_file, fallback)
        with open(fallback, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["product_url"])
            for url in sorted(all_product_urls):
                writer.writerow([url])

    logging.info("=== Collection Complete ===")
    logging.info("Total unique product URLs: %d", len(all_product_urls))


if __name__ == "__main__":
    collect_all_product_urls()

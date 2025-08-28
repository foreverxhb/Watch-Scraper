# watch_scraper.py
import time
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ---------- Config ----------
SEARCH_URL = "https://www.flipkart.com/search?q=Watches+for+Men+under+2000"
HTML_SAVE_PATH = "flipkart_watches_page.html"
EXCEL_OUTPUT = "watches.xlsx"
MAX_PRICE = 2000
SELENIUM_HEADLESS = True
# ----------------------------


def init_selenium(headless=SELENIUM_HEADLESS):
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    if headless:
        # use the new headless flag where available
        try:
            opts.add_argument("--headless=new")
        except Exception:
            opts.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    return driver


def fetch_page_with_driver(driver, url, wait=3):
    """Use Selenium driver to load URL and return rendered HTML"""
    driver.get(url)
    time.sleep(wait)  # allow JS to render
    return driver.page_source


def parse_price_text(price_text):
    if not price_text:
        return None
    digits = re.sub(r"[^\d]", "", price_text)
    try:
        return int(digits) if digits else None
    except:
        return None


def availability_from_soup(soup):
    """
    Return 'in stock' or 'out of stock' (lowercase) based on heuristics scanning the soup.
    Priority:
      - explicit out-of-stock phrases -> 'out of stock'
      - explicit in-stock actions (Add to Cart/Buy Now) -> 'in stock'
      - fallback -> 'out of stock'
    """
    # Normalize page text
    page_text = soup.get_text(" ", strip=True).lower()

    # Out-of-stock keywords (strong indicators)
    out_keywords = [
        "out of stock",
        "sold out",
        "notify me",
        "notify for",
        "currently unavailable",
        "temporarily out of stock",
        "coming soon",
        "unavailable",
        "notify when available",
        "out of inventory"
    ]
    for kw in out_keywords:
        if kw in page_text:
            return "out of stock"

    # Look at button texts for in-stock signals
    in_button_phrases = ["add to cart", "buy now", "add to bag", "add to basket", "add to trolley"]
    for btn in soup.find_all("button"):
        t = btn.get_text(" ", strip=True).lower()
        for p in in_button_phrases:
            if p in t:
                return "in stock"

    # Also check anchor texts sometimes used as action links
    for a in soup.find_all("a"):
        t = a.get_text(" ", strip=True).lower()
        for p in in_button_phrases:
            if p in t:
                return "in stock"

    # Another check: some pages show "Buy" or "Add" in other elements
    for tag in soup.find_all(["span", "div"]):
        t = tag.get_text(" ", strip=True).lower()
        for p in in_button_phrases:
            if p in t:
                return "in stock"

    # If nothing decisive, fallback to out of stock
    return "out of stock"


def get_availability(product_url, selenium_driver=None):
    """
    Try with requests first (fast). If that yields no decisive result (shouldn't happen with the heuristics),
    and a selenium_driver is provided, render with Selenium and re-evaluate.
    Returns 'in stock' or 'out of stock'.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:
        resp = requests.get(product_url, headers=headers, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            result = availability_from_soup(soup)
            # If the result is decisive (either in or out) - return it
            if result in ("in stock", "out of stock"):
                return result
        # If non-200 or not decisive, try Selenium if available
    except Exception:
        # fall through to selenium fallback if provided
        pass

    # Selenium fallback (more reliable if site renders availability with JS)
    if selenium_driver:
        try:
            html = fetch_page_with_driver(selenium_driver, product_url, wait=3)
            soup = BeautifulSoup(html, "lxml")
            return availability_from_soup(soup)
        except Exception:
            return "out of stock"

    # final fallback
    return "out of stock"


def parse_search_page(html):
    """Parse the search results HTML to extract product cards"""
    soup = BeautifulSoup(html, "lxml")

    # Use selectors discovered in your uploaded HTML
    # container selector: div._75nlfW
    containers = soup.select("div._75nlfW")
    items = []
    for c in containers:
        # Name / Title
        name_el = c.select_one("a.WKTcLC")
        name = name_el.get_text(strip=True) if name_el else ""

        # Brand
        brand_el = c.select_one("div.KzDlHZ")
        brand = brand_el.get_text(strip=True) if brand_el else (name.split()[0] if name else "")

        # Price
        price_el = c.select_one("div.Nx9bqj")
        price = parse_price_text(price_el.get_text(" ", strip=True)) if price_el else None

        # Product link
        href = name_el["href"] if name_el and name_el.has_attr("href") else None
        link = urljoin("https://www.flipkart.com", href) if href else ""

        # filter by price
        if not price or price > MAX_PRICE:
            continue

        items.append({
            "name": name,
            "brand": brand,
            "price": price,
            "link": link
        })

    return items


def main():
    driver = None
    try:
        # init selenium driver and fetch search page
        driver = init_selenium(headless=SELENIUM_HEADLESS)
        print("[*] Loading Flipkart search page (Selenium)...")
        search_html = fetch_page_with_driver(driver, SEARCH_URL, wait=5)

        # save raw html
        with open(HTML_SAVE_PATH, "w", encoding="utf-8") as f:
            f.write(search_html)
        print(f"[+] Saved search HTML to {HTML_SAVE_PATH}")

        # parse search page
        products = parse_search_page(search_html)
        print(f"[*] Found {len(products)} products (filtered by price <= {MAX_PRICE})")

        results = []
        for idx, p in enumerate(products, start=1):
            print(f"Checking ({idx}/{len(products)}): {p['name']} | ₹{p['price']}")
            # check availability using both requests (fast) and selenium fallback
            avail = get_availability(p["link"], selenium_driver=driver)
            # return lowercase exact strings requested: "in stock" / "out of stock"
            if avail != "in stock":
                avail = "out of stock"
            print(f" -> availability: {avail}")

            results.append({
                "Watch Name": p["name"],
                "Brand": p["brand"],
                "Price": p["price"],
                "Availability": avail,
                "Link": p["link"]
            })

            # polite pause
            time.sleep(1.0)

        # write to excel
        df = pd.DataFrame(results)
        df.to_excel(EXCEL_OUTPUT, index=False)
        print(f"[+] Saved {len(results)} items to {EXCEL_OUTPUT}")

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()

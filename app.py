import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import io
import re
import gc
import os
import random

# ================= CONFIG =================
st.set_page_config(page_title="Amazon Scraper PRO", layout="wide")
st.title("🛒 Amazon Global Scraper PRO")

TEMP_FILE = "temp_progress.xlsx"

# ================= AMAZON DOMAINS =================
AMAZON_DOMAINS = {
    "Egypt 🇪🇬 (.eg)": "www.amazon.eg",
    "USA 🇺🇸 (.com)": "www.amazon.com",
    "UK 🇬🇧 (.co.uk)": "www.amazon.co.uk",
    "UAE 🇦🇪 (.ae)": "www.amazon.ae",
    "Saudi 🇸🇦 (.sa)": "www.amazon.sa",
    "Germany 🇩🇪 (.de)": "www.amazon.de",
    "France 🇫🇷 (.fr)": "www.amazon.fr",
    "Italy 🇮🇹 (.it)": "www.amazon.it",
    "Spain 🇪🇸 (.es)": "www.amazon.es",
    "Netherlands 🇳🇱 (.nl)": "www.amazon.nl",
    "Poland 🇵🇱 (.pl)": "www.amazon.pl",
    "Sweden 🇸🇪 (.se)": "www.amazon.se",
    "Turkey 🇹🇷 (.com.tr)": "www.amazon.com.tr",
    "India 🇮🇳 (.in)": "www.amazon.in",
    "Japan 🇯🇵 (.co.jp)": "www.amazon.co.jp",
    "Canada 🇨🇦 (.ca)": "www.amazon.ca",
    "Australia 🇦🇺 (.com.au)": "www.amazon.com.au",
    "Singapore 🇸🇬 (.sg)": "www.amazon.sg",
    "Brazil 🇧🇷 (.com.br)": "www.amazon.com.br",
    "Mexico 🇲🇽 (.com.mx)": "www.amazon.com.mx",
    "South Africa 🇿🇦 (.co.za)": "www.amazon.co.za"
}

# ================= DRIVER =================
def get_driver():
    options = Options()
    # options.add_argument('--headless')  # disable if blocked
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

# ================= HELPERS =================
def wait_for_page(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "productTitle"))
        )
    except:
        pass

def get_text(driver, selectors):
    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.text.strip():
                return el.text.strip()
        except:
            continue
    return ""

def build_product_url(asin, domain):
    return f"https://{domain}/dp/{asin}"

def build_urls_from_asins(asins, domain):
    return [build_product_url(a.strip().split("/")[-1], domain) for a in asins]

def clean_urls(urls):
    asins = []
    for url in urls:
        if "/dp/" in url:
            asin = url.split("/dp/")[1].split("/")[0]
            asins.append(asin)
    return asins

# ================= IMAGES =================
def get_images(driver):
    images = set()

    for img in driver.find_elements(By.CSS_SELECTOR, "img"):
        data = img.get_attribute("data-a-dynamic-image")
        if data:
            matches = re.findall(r'"(https:[^"]+)"', data)
            images.update(matches)

    for img in driver.find_elements(By.CSS_SELECTOR, "#altImages img"):
        src = img.get_attribute("src")
        if src:
            images.add(re.sub(r"\._.*_\.", ".", src))

    return list(images)[:7]

# ================= PRODUCT =================
def get_product(driver, url):
    driver.get(url)
    wait_for_page(driver)
    time.sleep(random.uniform(2, 4))

    title = get_text(driver, ["#productTitle"])
    brand = get_text(driver, ["#bylineInfo", "#brand"])

    breadcrumb = [a.text.strip() for a in driver.find_elements(By.CSS_SELECTOR, "#wayfinding-breadcrumbs_feature_div a")]

    bullets = [li.text.strip() for li in driver.find_elements(By.CSS_SELECTOR, "#feature-bullets li") if li.text.strip()]

    description = get_text(driver, [
        "#productDescription",
        "#aplus_feature_div",
        "#feature-bullets"
    ])

    images = get_images(driver)

    return {
        "URL": url,
        "Title": title,
        "Brand": brand,
        "Breadcrumb": ", ".join(breadcrumb),
        "About": "; ".join(bullets),
        "Description": description,
        **{f"Image {i+1}": img for i, img in enumerate(images)}
    }

# ================= SELLER =================
def extract_seller(driver, seller_url, domain):
    urls = []
    page = seller_url

    while page:
        driver.get(page)
        time.sleep(4)

        items = driver.find_elements(By.CSS_SELECTOR, "div[data-asin]")
        for item in items:
            asin = item.get_attribute("data-asin")
            if asin:
                urls.append(build_product_url(asin, domain))

        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "a.s-pagination-next")
            if "disabled" in next_btn.get_attribute("class"):
                break
            page = next_btn.get_attribute("href")
        except:
            break

    return list(set(urls))

# ================= UI =================
mode = st.selectbox("Mode", ["ASINs", "Product URLs", "Seller Store"])

country = st.selectbox("Country", list(AMAZON_DOMAINS.keys()))
domain = AMAZON_DOMAINS[country]

if mode == "Seller Store":
    seller_url = st.text_input("Seller URL")
else:
    user_input = st.text_area("Input (one per line)")

# ================= RUN =================
if st.button("🚀 Start"):

    final_urls = []

    if mode == "ASINs":
        asins = [x.strip() for x in user_input.split("\n") if x.strip()]
        final_urls = build_urls_from_asins(asins, domain)

    elif mode == "Product URLs":
        urls = [x.strip() for x in user_input.split("\n") if x.strip()]
        asins = clean_urls(urls)
        final_urls = build_urls_from_asins(asins, domain)

    elif mode == "Seller Store":
        driver = get_driver()
        final_urls = extract_seller(driver, seller_url, domain)
        driver.quit()

    if not final_urls:
        st.warning("No URLs found")
        st.stop()

    # ===== RESUME =====
    if os.path.exists(TEMP_FILE):
        df_old = pd.read_excel(TEMP_FILE)
        done = set(df_old["URL"])
        final_urls = [u for u in final_urls if u not in done]
        results = df_old.to_dict("records")
        st.info(f"Resuming... {len(done)} already done")
    else:
        results = []

    progress = st.progress(0)

    for i, url in enumerate(final_urls):
        st.write(f"{i+1}/{len(final_urls)}")

        for _ in range(2):
            driver = get_driver()
            try:
                data = get_product(driver, url)
                results.append(data)
                driver.quit()
                break
            except:
                driver.quit()

        pd.DataFrame(results).to_excel(TEMP_FILE, index=False)

        progress.progress((i + 1) / len(final_urls))
        gc.collect()

    df = pd.DataFrame(results)
    st.dataframe(df)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)

    st.download_button("📥 Download Excel", buffer.getvalue(), "amazon.xlsx")

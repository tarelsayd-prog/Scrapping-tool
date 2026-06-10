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
import shutil
import re
import gc
import os
import random

# --- CONFIG ---
st.set_page_config(page_title="Amazon Scraper PRO", layout="wide")
st.title("🛒 Amazon Scraper PRO (Stable Version)")

TEMP_FILE = "temp_progress.xlsx"

# --- DRIVER SETUP ---
def get_driver():
    options = Options()
    # ⚠️ Headless OFF for better scraping
    # options.add_argument('--headless')

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    )

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

# --- WAIT ---
def wait_for_page(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "productTitle"))
        )
    except:
        pass

# --- SAFE TEXT ---
def get_text(driver, selectors):
    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.text.strip():
                return el.text.strip()
        except:
            continue
    return ""

# --- IMAGES ---
def get_real_amazon_images(driver):
    image_urls = set()

    # Dynamic images
    imgs = driver.find_elements(By.CSS_SELECTOR, "img")
    for img in imgs:
        data = img.get_attribute("data-a-dynamic-image")
        if data:
            matches = re.findall(r'"(https:[^"]+)"', data)
            image_urls.update(matches)

    # Thumbnails fallback
    thumbs = driver.find_elements(By.CSS_SELECTOR, "#altImages img")
    for img in thumbs:
        src = img.get_attribute("src")
        if src:
            clean = re.sub(r"\._.*_\.", ".", src)
            image_urls.add(clean)

    return list(image_urls)[:7]

# --- PRODUCT SCRAPER ---
def get_product_details(driver, url):
    driver.get(url)
    wait_for_page(driver)

    time.sleep(random.uniform(2, 4))

    title = get_text(driver, ["#productTitle"])
    brand = get_text(driver, ["#bylineInfo", "#brand"])

    breadcrumb = []
    try:
        breadcrumb = [
            a.text.strip()
            for a in driver.find_elements(By.CSS_SELECTOR, "#wayfinding-breadcrumbs_feature_div a")
        ]
    except:
        pass

    about = []
    for li in driver.find_elements(By.CSS_SELECTOR, "#feature-bullets li"):
        txt = li.text.strip()
        if txt:
            about.append(txt)

    description = get_text(driver, [
        "#productDescription",
        "#aplus_feature_div",
        "#feature-bullets"
    ])

    images = get_real_amazon_images(driver)

    details = {}
    for row in driver.find_elements(By.CSS_SELECTOR, "#detailBullets_feature_div li"):
        txt = row.text.strip()
        if ":" in txt:
            k, v = txt.split(":", 1)
            details[k.strip()] = v.strip()

    specs = {}
    for row in driver.find_elements(By.CSS_SELECTOR, "#productDetails_techSpec_section_1 tr"):
        try:
            specs[row.find_element(By.TAG_NAME, "th").text.strip()] = \
                row.find_element(By.TAG_NAME, "td").text.strip()
        except:
            pass

    images_dict = {f"Image {i+1}": img for i, img in enumerate(images)}

    return {
        "URL": url,
        "Title": title,
        "Brand": brand,
        "Breadcrumb": ", ".join(breadcrumb),
        "About": "; ".join(about),
        "Description": description,
        **images_dict,
        **details,
        **specs
    }

# --- RETRY ---
def safe_scrape(url):
    for _ in range(2):
        driver = get_driver()
        try:
            data = get_product_details(driver, url)
            driver.quit()
            return data
        except:
            driver.quit()
    return {"URL": url}

# --- UI ---
urls_input = st.text_area("Paste Amazon URLs (one per line):")

if st.button("🚀 Start Scraping"):

    urls = [u.strip() for u in urls_input.split("\n") if u.strip()]

    if not urls:
        st.warning("Enter URLs first")
        st.stop()

    # --- RESUME ---
    if os.path.exists(TEMP_FILE):
        existing_df = pd.read_excel(TEMP_FILE)
        done_urls = set(existing_df["URL"].tolist())
        urls = [u for u in urls if u not in done_urls]
        results = existing_df.to_dict("records")
        st.info(f"Resuming: {len(done_urls)} already done")
    else:
        results = []

    progress = st.progress(0)

    for i, url in enumerate(urls):
        st.write(f"Processing {i+1}/{len(urls)}")

        data = safe_scrape(url)
        results.append(data)

        # SAVE PROGRESS EVERY ITEM
        pd.DataFrame(results).to_excel(TEMP_FILE, index=False)

        progress.progress((i + 1) / len(urls))
        gc.collect()

    st.success("✅ Done!")

    df = pd.DataFrame(results)
    st.dataframe(df)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)

    st.download_button(
        "📥 Download Excel",
        buffer.getvalue(),
        "amazon_results.xlsx"
    )

import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import io
import re
import gc
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Amazon Scraper Hub", layout="wide")
st.title("🛒 Amazon Global Automated Scraper")

AMAZON_DOMAINS = {
    "Egypt (.eg)": "www.amazon.eg", "United States (.com)": "www.amazon.com",
    "United Arab Emirates (.ae)": "www.amazon.ae", "Saudi Arabia (.sa)": "www.amazon.sa",
    "United Kingdom (.co.uk)": "www.amazon.co.uk", "Germany (.de)": "www.amazon.de",
    "France (.fr)": "www.amazon.fr", "Italy (.it)": "www.amazon.it",
    "Spain (.es)": "www.amazon.es", "Canada (.ca)": "www.amazon.ca",
    "Mexico (.com.mx)": "www.amazon.com.mx", "Brazil (.com.br)": "www.amazon.com.br",
    "India (.in)": "www.amazon.in", "Japan (.co.jp)": "www.amazon.co.jp",
    "Australia (.com.au)": "www.amazon.com.au"
}

# --- THE PERFECT STREAMLIT CLOUD SELENIUM SETUP ---
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage') # Prevents RAM crashes
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    # HARDCODED FOR STREAMLIT CLOUD LINUX SERVER
    # This completely bypasses driver mismatches
    options.binary_location = "/usr/bin/chromium"
    service = Service("/usr/bin/chromedriver")
        
    return webdriver.Chrome(service=service, options=options)

# --- LAYER 1: MULTI-PAGE SELLER LINK EXTRACTION ---
def extract_seller_urls(driver, seller_url, status_element):
    product_urls = []
    current_url = seller_url
    page_num = 1
    
    while current_url:
        status_element.text(f"🏬 Storefront: Extracting page {page_num}...")
        driver.get(current_url)
        time.sleep(4)
        
        items = driver.find_elements(By.CSS_SELECTOR, "div[data-asin]")
        page_items_count = 0 
        
        for item in items:
            asin = item.get_attribute("data-asin")
            if asin and len(asin) > 5:
                product_urls.append(f"https://www.amazon.eg/dp/{asin}")
                page_items_count += 1
                
        if page_items_count == 0: break
            
        try:
            next_button = driver.find_elements(By.CSS_SELECTOR, "a.s-pagination-next")
            if next_button and "s-pagination-disabled" not in next_button[0].get_attribute("class"):
                current_url = next_button[0].get_attribute("href")
                page_num += 1
            else:
                current_url = None
        except:
            current_url = None
            
    return list(dict.fromkeys(product_urls))

# --- LAYER 2: ROBUST IMAGE EXTRACTION ---
def get_real_amazon_images(driver):
    image_urls = []
    try:
        scripts = driver.find_elements(By.TAG_NAME, "script")
        for script in scripts:
            content = script.get_attribute("innerHTML")
            if content and "colorImages" in content:
                hires = re.findall(r'"hiRes":"(https:[^"]+)"', content)
                large = re.findall(r'"large":"(https:[^"]+)"', content)
                main = re.findall(r'"mainUrl":"(https:[^"]+)"', content)
                if hires: image_urls.extend(hires)
                elif large: image_urls.extend(large)
                elif main: image_urls.extend(main)
                break
        if not image_urls:
            thumbnails = driver.find_elements(By.CSS_SELECTOR, "#altImages img")
            for img in thumbnails:
                src = img.get_attribute("src")
                if src: image_urls.append(re.sub(r"\._.*_\.", ".", src))
    except:
        pass 
    return list(set([img for img in image_urls if img and img != "null"]))[:7]

# --- LAYER 3: PRODUCT DEEP DETAILS SCRAPER ---
def get_product_details(driver, url):
    driver.get(url)
    time.sleep(4)  
    
    real_images = get_real_amazon_images(driver)
    
    title = driver.find_element(By.CSS_SELECTOR, "#productTitle").text.strip() if driver.find_elements(By.CSS_SELECTOR, "#productTitle") else "None"
    brand = driver.find_element(By.CSS_SELECTOR, "#bylineInfo").text.strip() if driver.find_elements(By.CSS_SELECTOR, "#bylineInfo") else "None"
    
    breadcrumb = []
    breadcrumb_el = driver.find_elements(By.CSS_SELECTOR, "#wayfinding-breadcrumbs_feature_div ul")
    if breadcrumb_el:
        breadcrumb = [a.text.strip() for a in breadcrumb_el[0].find_elements(By.TAG_NAME, 'a')]

    about_items = []
    about_el = driver.find_elements(By.CSS_SELECTOR, "#feature-bullets ul")
    if about_el:
        about_items = [li.text.strip() for li in about_el[0].find_elements(By.TAG_NAME, 'li')]

    product_description = driver.find_element(By.CSS_SELECTOR, "#productDescription").text.strip() if driver.find_elements(By.CSS_SELECTOR, "#productDescription") else "None"
        
    details_dict = {}
    for row in driver.find_elements(By.CSS_SELECTOR, "#detailBullets_feature_div li"):
        text = row.text.strip()
        if ":" in text:
            key, value = text.split(":", 1)
            details_dict[key.strip()] = value.strip()

    tech_specs_dict = {}
    for row in driver.find_elements(By.CSS_SELECTOR, "#productDetails_techSpec_section_1 tr"):
        try:
            tech_specs_dict[row.find_element(By.TAG_NAME, "th").text.strip()] = row.find_element(By.TAG_NAME, "td").text.strip()
        except: pass
            
    images_dict = {f"Image {i+1}": img for i, img in enumerate(real_images)}
    
    return {
        "URL": url, "Title": title, "Brand": brand, "Breadcrumb": ", ".join(breadcrumb),
        "About This Item": "; ".join(about_items), "Product Description": product_description,
        **images_dict, **details_dict, **tech_specs_dict
    }

# --- UI & EXECUTION ---
st.markdown("### 🛠️ Configuration Panel")
scrape_mode = st.selectbox("Choose Scrape Operation Mode:", ["Option 1: Direct URLs / ASINs", "Option 2: Seller Storefront"])

input_format = "Full URLs"
selected_domain = "www.amazon.eg"

if "Option 1" in scrape_mode:
    input_format = st.radio("Input Type:", ["Full URLs", "ASINs"], horizontal=True)
    if input_format == "ASINs":
        region_name = st.selectbox("Select Amazon Region:", list(AMAZON_DOMAINS.keys()), index=0)
        selected_domain = AMAZON_DOMAINS[region_name]

    col1, col2 = st.columns(2)
    with col1: urls_input = st.text_area(f"Paste {input_format} here (one per line):", height=150)
    with col2: uploaded_file = st.file_uploader(f"Or upload Excel/CSV", type=['csv', 'xlsx'])
else:
    seller_input = st.text_input("Paste Amazon Seller Storefront URL:")

st.divider()

if st.button("Run Extraction Pipeline", type="primary"):
    status_text = st.empty()
    final_urls = []
    
    if "Option 1" in scrape_mode:
        raw_inputs = []
        if urls_input: raw_inputs.extend([v.strip() for v in urls_input.split('\n') if v.strip()])
        if uploaded_file:
            try:
                df_input = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                val_col = df_input.columns[0] # Grabs the first column automatically
                raw_inputs.extend([str(v).strip() for v in df_input[val_col].dropna().tolist() if str(v).strip()])
            except: st.error("Error reading file.")
        
        combined_urls = []
        if input_format == "ASINs":
            for val in raw_inputs:
                clean_asin = val.split('/')[-1] if 'amazon' in val.lower() else val
                combined_urls.append(f"https://{selected_domain}/dp/{clean_asin}")
        else: combined_urls = raw_inputs

        final_urls = list(dict.fromkeys(combined_urls))
            
    elif "Option 2" in scrape_mode and seller_input:
        store_driver = get_driver()
        try:
            with st.spinner("Processing storefront..."):
                final_urls = extract_seller_urls(store_driver, seller_input, status_text)
        finally:
            store_driver.quit()
            gc.collect()

    if final_urls:
        results = []
        progress_bar = st.progress(0)
        
        for index, url in enumerate(final_urls):
            status_text.text(f"📦 Scraping {index + 1}/{len(final_urls)}: {url}")
            
            # MEMORY SAVER: Fresh browser for each link
            single_driver = get_driver()
            try:
                results.append(get_product_details(single_driver, url))
            except Exception as e:
                pass # Skip silently if a page fails
            finally:
                single_driver.quit()
                gc.collect()
            
            progress_bar.progress((index + 1) / len(final_urls))
            
        status_text.success("✨ Extraction Complete!")
        
        if results:
            df = pd.DataFrame(results)
            st.dataframe(df)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Data')
            st.download_button("📥 Download Excel", data=buffer.getvalue(), file_name="amazon_data.xlsx")
    else:
        st.warning("No valid URLs found to process.")

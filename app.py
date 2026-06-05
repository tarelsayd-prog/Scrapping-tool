import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import io
import shutil
import re

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Amazon Scraper Hub", layout="wide")
st.title("🛒 Amazon Egypt Automated Scraper Hub")

# --- SELENIUM HEADLESS SETUP (LOW MEMORY MODE) ---
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage') # Crucial for low-RAM Linux servers
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')    # Strips out extra memory usage
    options.add_argument('--disable-infobars')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    chromium_path = shutil.which('chromium')
    chromedriver_path = shutil.which('chromedriver')
    
    if chromium_path and chromedriver_path:
        options.binary_location = chromium_path
        service = Service(chromedriver_path)
    else:
        service = Service(ChromeDriverManager().install())
        
    return webdriver.Chrome(service=service, options=options)

# --- LAYER 1: MULTI-PAGE SELLER LINK EXTRACTION ---
def extract_seller_urls(driver, seller_url, status_element):
    product_urls = []
    current_url = seller_url
    page_num = 1
    
    while current_url:
        status_element.text(f"🏬 Storefront: Extracting page {page_num}...")
        driver.get(current_url)
        time.sleep(5)
        
        items = driver.find_elements(By.CSS_SELECTOR, "div[data-asin]")
        page_items_count = 0 
        
        for item in items:
            asin = item.get_attribute("data-asin")
            if asin and len(asin) > 5:
                product_urls.append(f"https://www.amazon.eg/dp/{asin}")
                page_items_count += 1
                
        if page_items_count == 0:
            break
            
        try:
            next_button = driver.find_elements(By.CSS_SELECTOR, "a.s-pagination-next")
            if next_button and "s-pagination-disabled" not in next_button[0].get_attribute("class"):
                current_url = next_button[0].get_attribute("href")
                page_num += 1
            else:
                current_url = None
        except Exception:
            current_url = None
            
    return list(dict.fromkeys(product_urls))

# --- LAYER 2: ROBUST IMAGE EXTRACTION ---
def get_real_amazon_images(driver):
    image_urls = []
    try:
        thumbs = driver.find_elements(By.CSS_SELECTOR, "#altImages li img")
        for t in thumbs:
            try:
                t.click()
                time.sleep(0.3)
            except:
                pass

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
                if src:
                    image_urls.append(re.sub(r"\._.*_\.", ".", src))
    except Exception:
        pass 
    return list(set([img for img in image_urls if img and img != "null"]))[:7]

# --- LAYER 3: PRODUCT DEEP DETAILS SCRAPER ---
def get_product_details(driver, url):
    driver.get(url)
    time.sleep(5)  
    
    real_images = get_real_amazon_images(driver)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
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
        except:
            pass
            
    images_dict = {f"Image {i+1}": img for i, img in enumerate(real_images)}
    
    return {
        "URL": url, "Title": title, "Brand": brand, "Breadcrumb": ", ".join(breadcrumb),
        "About This Item": "; ".join(about_items), "Product Description": product_description,
        **images_dict, **details_dict, **tech_specs_dict
    }

# --- CONTROL USER INTERFACE ---
st.markdown("### 🛠️ Configuration Panel")
scrape_mode = st.selectbox(
    "Choose Scrape Operation Mode:",
    ["Option 1: Direct Product Scraping (Input URLs / Upload File)", 
     "Option 2: Full Seller Storefront Scraping (Auto-extract Links + Scrape Details)"]
)

# --- CONDITIONAL INTERFACE LAYOUT ---
if "Option 1" in scrape_mode:
    col1, col2 = st.columns(2)
    with col1:
        urls_input = st.text_area("Paste Product URLs here (one per line):", height=150)
    with col2:
        uploaded_file = st.file_uploader("Or upload an Excel / CSV file containing URLs", type=['csv', 'xlsx'])
else:
    seller_input = st.text_input("Paste Amazon Seller Storefront URL (e.g., https://www.amazon.eg/s?me=...):")

st.divider()

# --- EXECUTION ENGINE ---
if st.button("Run Extraction Pipeline", type="primary"):
    status_text = st.empty()
    final_urls = []
    should_continue = True
    
    # 1. Process inputs BEFORE turning on the heavy browser to save memory
    if "Option 1" in scrape_mode:
        combined_urls = []
        if urls_input:
            combined_urls.extend([url.strip() for url in urls_input.split('\n') if url.strip()])
        if uploaded_file is not None:
            try:
                df_input = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                url_col = next((col for col in df_input.columns if str(col).strip().lower() in ['url', 'urls', 'link', 'links']), df_input.columns[0])
                combined_urls.extend([url.strip() for url in df_input[url_col].dropna().astype(str).tolist() if url.strip()])
            except Exception as e:
                st.error(f"Error parsing uploaded file: {e}")
                should_continue = False
        
        final_urls = list(dict.fromkeys(combined_urls))
        if not final_urls and should_continue:
            st.warning("Please enter URLs or upload a valid file.")
            should_continue = False
            
    else: # Option 2 Execution validation
        if not seller_input:
            st.warning("Please enter a valid seller URL.")
            should_continue = False

    # 2. Start the heavy scraping engine ONLY if we have valid inputs
    if should_continue:
        driver = get_driver() # Turn on the browser
        
        try: # << CRITICAL: This try block ensures the browser ALWAYS closes, preventing memory crashes
        
            if "Option 2" in scrape_mode:
                with st.spinner("Processing storefront mapping..."):
                    final_urls = extract_seller_urls(driver, seller_input, status_text)
                    st.info(f"🏬 Storefront Map Complete: Discovered **{len(final_urls)}** target products.")

            # Core Detail Scraping Phase
            if not final_urls:
                st.warning("No operational URLs located. Check inputs.")
            else:
                results = []
                progress_bar = st.progress(0)
                
                for index, url in enumerate(final_urls):
                    status_text.text(f"📦 Progress: Processing item {index + 1} of {len(final_urls)} → {url}")
                    try:
                        results.append(get_product_details(driver, url))
                    except Exception as e:
                        st.error(f"Failed asset pull on {url}: {e}")
                    progress_bar.progress((index + 1) / len(final_urls))
                    
                status_text.success("✨ Processing pipeline finalized successfully!")
                
                if results:
                    df = pd.DataFrame(results)
                    st.dataframe(df)
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Master Catalog Data')
                    
                    st.download_button(
                        label="📥 Download Consolidated Master Dataset (Excel)",
                        data=buffer.getvalue(),
                        file_name="amazon_master_catalog_details.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
        finally:
            # << CRITICAL: No matter what happens above (success, crash, user cancellation)
            # This line will run and destroy the hidden browser to free up Streamlit's 1GB RAM limit.
            driver.quit()

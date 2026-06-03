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

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Amazon Scraper", layout="wide")
st.title("🛒 Amazon Egypt Product Scraper")
st.markdown("Enter Amazon Egypt product URLs below or upload a file to extract details and download them as an Excel file.")

# --- SELENIUM HEADLESS SETUP ---
@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    # Spoofing user agent to help avoid bot detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    # Check if the system has Chromium installed (Streamlit Cloud uses Debian Linux)
    chromium_path = shutil.which('chromium')
    chromedriver_path = shutil.which('chromedriver')
    
    if chromium_path and chromedriver_path:
        # If found, force Selenium to use these exact files to prevent version crashes
        options.binary_location = chromium_path
        service = Service(chromedriver_path)
    else:
        # Fallback to the webdriver-manager if you ever run this locally on your own computer
        service = Service(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# --- SCRAPING FUNCTION ---
def get_product_details(driver, url):
    driver.get(url)
    time.sleep(5)  # Wait for JavaScript to load
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Extract Title
    title_elements = driver.find_elements(By.CSS_SELECTOR, "#productTitle")
    title = title_elements[0].text.strip() if title_elements else "None"

    # Extract Brand
    brand_elements = driver.find_elements(By.CSS_SELECTOR, "#bylineInfo")
    brand = brand_elements[0].text.strip() if brand_elements else "None"
    
    # Extract Breadcrumb
    breadcrumb_elements = driver.find_elements(By.CSS_SELECTOR, "#wayfinding-breadcrumbs_feature_div > ul")
    breadcrumb_items = [item.text.strip() for item in breadcrumb_elements[0].find_elements(By.TAG_NAME, 'a')] if breadcrumb_elements else ["No breadcrumb found"]

    # Extract "About this item"
    about_elements = driver.find_elements(By.CSS_SELECTOR, "#featurebullets_feature_div ul")
    about_items = [item.text.strip() for item in about_elements[0].find_elements(By.TAG_NAME, 'li')] if about_elements else ["No about this item found"]

    # Extract Image URL
    img_element = soup.find('img', {'id': 'landingImage'})
    image_url = img_element['src'] if img_element else 'N/A'

    # Extract Product Details (First 10)
    details = []
    for i in range(1, 11):
        detail = driver.find_elements(By.CSS_SELECTOR, f"#detailBullets_feature_div > ul > li:nth-child({i})")
        details.append(detail[0].text.strip() if detail else "None")
    
    # Extract Tech Specs (First 12)
    tech_specs = []
    for i in range(1, 13):
        spec = driver.find_elements(By.CSS_SELECTOR, f"#productDetails_techSpec_section_1 > tbody > tr:nth-child({i})")
        tech_specs.append(spec[0].text.strip() if spec else "None")
    
    # Extract Product Description
    desc_elements = driver.find_elements(By.CSS_SELECTOR, "#productDescription")
    product_description = desc_elements[0].text.strip() if desc_elements else "None"
    
    return {
        "URL": url, "Title": title, "Brand": brand, "Breadcrumb": " > ".join(breadcrumb_items), 
        "About This Item": " | ".join(about_items), "Image URL": image_url,
        "Detail 1": details[0], "Detail 2": details[1], "Detail 3": details[2], "Detail 4": details[3], "Detail 5": details[4],
        "Detail 6": details[5], "Detail 7": details[6], "Detail 8": details[7], "Detail 9": details[8], "Detail 10": details[9],
        "Tech Spec 1": tech_specs[0], "Tech Spec 2": tech_specs[1], "Tech Spec 3": tech_specs[2], "Tech Spec 4": tech_specs[3],
        "Tech Spec 5": tech_specs[4], "Tech Spec 6": tech_specs[5], "Tech Spec 7": tech_specs[6], "Tech Spec 8": tech_specs[7],
        "Tech Spec 9": tech_specs[8], "Tech Spec 10": tech_specs[9], "Tech Spec 11": tech_specs[10], "Tech Spec 12": tech_specs[11],
        "Product Description": product_description
    }

# --- USER INTERFACE ---
st.markdown("### 1. Input URLs")
col1, col2 = st.columns(2)

with col1:
    urls_input = st.text_area("Paste Amazon URLs here (one per line):", height=150)

with col2:
    uploaded_file = st.file_uploader("Or upload an Excel or CSV file containing URLs", type=['csv', 'xlsx'])
    st.caption("The app will look for a column named 'URL' or 'Link'. If not found, it will read the first column.")

st.divider()

if st.button("Start Scraping", type="primary"):
    combined_urls = []
    
    # 1. Process Text Input
    if urls_input:
        text_urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
        combined_urls.extend(text_urls)
        
    # 2. Process File Upload
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_input = pd.read_csv(uploaded_file)
            else:
                df_input = pd.read_excel(uploaded_file)
                
            # Attempt to find the correct column header
            url_col = None
            for col in df_input.columns:
                if str(col).strip().lower() in ['url', 'urls', 'link', 'links']:
                    url_col = col
                    break
            
            # Extract URLs from the found column, or default to the first column
            if url_col:
                file_urls = df_input[url_col].dropna().astype(str).tolist()
            else:
                file_urls = df_input.iloc[:, 0].dropna().astype(str).tolist()
                
            combined_urls.extend([url.strip() for url in file_urls if url.strip()])
            
        except Exception as e:
            st.error(f"Error reading the uploaded file: {e}")
            st.stop()

    # 3. Remove duplicates while preserving the order
    final_urls = list(dict.fromkeys(combined_urls))
    
    if not final_urls:
        st.warning("Please enter at least one URL or upload a valid file.")
    else:
        st.info(f"Total unique URLs to scrape: **{len(final_urls)}**")
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        driver = get_driver()
        
        for index, url in enumerate(final_urls):
            status_text.text(f"Scraping {index + 1} of {len(final_urls)}: {url}")
            try:
                data = get_product_details(driver, url)
                results.append(data)
            except Exception as e:
                st.error(f"Error scraping {url}: {e}")
            
            # Update progress bar
            progress_bar.progress((index + 1) / len(final_urls))
            
        status_text.text("Scraping complete!")
        
        if results:
            df = pd.DataFrame(results)
            st.success("Successfully scraped the data!")
            st.dataframe(df) # Preview the data
            
            # Convert DataFrame to Excel in memory
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Scraped Data')
            
            # Download Button
            st.download_button(
                label="📥 Download Data as Excel",
                data=buffer.getvalue(),
                file_name="amazon_product_details.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

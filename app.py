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

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Amazon Scraper", layout="wide")
st.title("🛒 Amazon Egypt Product Scraper")
st.markdown("Enter Amazon Egypt product URLs below to extract details and download them as an Excel file.")

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
default_urls = "https://www.amazon.eg/dp/B0C6KTLVLM/ref?th=1&language=en_AE\nhttps://www.amazon.eg/dp/B091CZR4RC/ref?th=1&language=en_AE"
urls_input = st.text_area("Paste Amazon URLs here (one per line):", value=default_urls, height=150)

if st.button("Start Scraping", type="primary"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if not urls:
        st.warning("Please enter at least one URL.")
    else:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        driver = get_driver()
        
        for index, url in enumerate(urls):
            status_text.text(f"Scraping {index + 1} of {len(urls)}: {url}")
            try:
                data = get_product_details(driver, url)
                results.append(data)
            except Exception as e:
                st.error(f"Error scraping {url}: {e}")
            
            # Update progress bar
            progress_bar.progress((index + 1) / len(urls))
            
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
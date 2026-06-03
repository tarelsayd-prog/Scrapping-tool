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
st.set_page_config(page_title="Amazon Scraper", layout="wide")
st.title("🛒 Amazon Egypt Scraper Hub")

# --- SELENIUM HEADLESS SETUP ---
@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    # Spoofing user agent to help avoid bot detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    # Check if the system has Chromium installed (Streamlit Cloud uses Debian Linux)
    chromium_path = shutil.which('chromium')
    chromedriver_path = shutil.which('chromedriver')
    
    if chromium_path and chromedriver_path:
        options.binary_location = chromium_path
        service = Service(chromedriver_path)
    else:
        service = Service(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# --- IMAGE EXTRACTION (ROBUST VERSION) ---
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
                    high_res = re.sub(r"\._.*_\.", ".", src)
                    image_urls.append(high_res)
    except Exception:
        pass 

    image_urls = list(set([img for img in image_urls if img and img != "null"]))
    return image_urls[:7]

# --- SCRAPING FUNCTION: PRODUCT DETAILS ---
def get_product_details(driver, url):
    driver.get(url)
    time.sleep(5)  
    
    real_images = get_real_amazon_images(driver)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    title = "None"
    if driver.find_elements(By.CSS_SELECTOR, "#productTitle"):
        title = driver.find_element(By.CSS_SELECTOR, "#productTitle").text.strip()

    brand = "None"
    if driver.find_elements(By.CSS_SELECTOR, "#bylineInfo"):
        brand = driver.find_element(By.CSS_SELECTOR, "#bylineInfo").text.strip()
    
    breadcrumb = []
    breadcrumb_el = driver.find_elements(By.CSS_SELECTOR, "#wayfinding-breadcrumbs_feature_div ul")
    if breadcrumb_el:
        links = breadcrumb_el[0].find_elements(By.TAG_NAME, 'a')
        breadcrumb = [a.text.strip() for a in links]

    about_items = []
    about_el = driver.find_elements(By.CSS_SELECTOR, "#feature-bullets ul")
    if about_el:
        lis = about_el[0].find_elements(By.TAG_NAME, 'li')
        about_items = [li.text.strip() for li in lis]

    product_description = "None"
    if driver.find_elements(By.CSS_SELECTOR, "#productDescription"):
        product_description = driver.find_element(By.CSS_SELECTOR, "#productDescription").text.strip()
        
    details_dict = {}
    details_rows = driver.find_elements(By.CSS_SELECTOR, "#detailBullets_feature_div li")
    for row in details_rows:
        text = row.text.strip()
        if ":" in text:
            key, value = text.split(":", 1)
            details_dict[key.strip()] = value.strip()

    tech_specs_dict = {}
    tech_rows = driver.find_elements(By.CSS_SELECTOR, "#productDetails_techSpec_section_1 tr")
    for row in tech_rows:
        try:
            th = row.find_element(By.TAG_NAME, "th").text.strip()
            td = row.find_element(By.TAG_NAME, "td").text.strip()
            tech_specs_dict[th] = td
        except:
            pass
            
    images_dict = {f"Image {i+1}": img for i, img in enumerate(real_images)}
    
    product_data = {
        "URL": url,
        "Title": title,
        "Brand": brand,
        "Breadcrumb": ", ".join(breadcrumb),
        "About This Item": "; ".join(about_items),
        "Product Description": product_description,
        **images_dict,
        **details_dict,
        **tech_specs_dict
    }
    
    return product_data

# --- SCRAPING FUNCTION: SELLER PAGE URLS ---
def extract_seller_urls(driver, seller_url):
    driver.get(seller_url)
    time.sleep(5) # Wait for page to load
    
    # Amazon search/seller pages list products in divs with a 'data-asin' attribute
    items = driver.find_elements(By.CSS_SELECTOR, "div[data-asin]")
    
    product_urls = []
    for item in items:
        asin = item.get_attribute("data-asin")
        # Ensure it's a valid ASIN (usually 10 characters) and not empty
        if asin and len(asin) > 5:
            # Construct a clean, standardized Amazon Egypt URL
            clean_url = f"https://www.amazon.eg/dp/{asin}"
            product_urls.append(clean_url)
            
    # Return unique URLs
    return list(dict.fromkeys(product_urls))


# --- USER INTERFACE: TABS ---
tab1, tab2 = st.tabs(["📦 Scrape Product Details", "🏬 Extract Links from Seller"])

# ==========================================
# TAB 1: PRODUCT DETAILS SCRAPER
# ==========================================
with tab1:
    st.markdown("### 1. Input Product URLs")
    col1, col2 = st.columns(2)

    with col1:
        urls_input = st.text_area("Paste Amazon Product URLs here (one per line):", height=150)

    with col2:
        uploaded_file = st.file_uploader("Or upload an Excel or CSV file containing URLs", type=['csv', 'xlsx'])
        st.caption("The app will look for a column named 'URL' or 'Link'. If not found, it will read the first column.")

    st.divider()

    if st.button("Start Scraping Products", type="primary"):
        combined_urls = []
        
        if urls_input:
            text_urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            combined_urls.extend(text_urls)
            
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_input = pd.read_csv(uploaded_file)
                else:
                    df_input = pd.read_excel(uploaded_file)
                    
                url_col = None
                for col in df_input.columns:
                    if str(col).strip().lower() in ['url', 'urls', 'link', 'links']:
                        url_col = col
                        break
                
                if url_col:
                    file_urls = df_input[url_col].dropna().astype(str).tolist()
                else:
                    file_urls = df_input.iloc[:, 0].dropna().astype(str).tolist()
                    
                combined_urls.extend([url.strip() for url in file_urls if url.strip()])
                
            except Exception as e:
                st.error(f"Error reading the uploaded file: {e}")
                st.stop()

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
                
                progress_bar.progress((index + 1) / len(final_urls))
                
            status_text.text("Scraping complete!")
            
            if results:
                df = pd.DataFrame(results)
                st.success("Successfully scraped the data!")
                st.dataframe(df) 
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Scraped Data')
                
                st.download_button(
                    label="📥 Download Data as Excel",
                    data=buffer.getvalue(),
                    file_name="amazon_dynamic_product_details.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# ==========================================
# TAB 2: SELLER LINK EXTRACTOR
# ==========================================
with tab2:
    st.markdown("### Extract Product Links from a Seller Storefront")
    st.markdown("Paste an Amazon Seller page link (e.g., `https://www.amazon.eg/s?me=...`). The app will find all the ASINs on that specific page and generate clean product URLs for you to copy into Tab 1.")
    
    seller_input = st.text_input("Seller Storefront URL:")
    
    if st.button("Extract Links", type="secondary"):
        if not seller_input:
            st.warning("Please enter a seller URL first.")
        else:
            with st.spinner("Navigating to seller page and extracting ASINs..."):
                driver = get_driver()
                try:
                    extracted_urls = extract_seller_urls(driver, seller_input)
                    
                    if extracted_urls:
                        st.success(f"Successfully extracted {len(extracted_urls)} product links!")
                        
                        # Display them in a text area so the user can easily CTRL+C them
                        formatted_urls = "\n".join(extracted_urls)
                        st.text_area("Extracted URLs (Copy these into Tab 1):", value=formatted_urls, height=300)
                        
                        # Provide a quick CSV download option for the links
                        df_links = pd.DataFrame(extracted_urls, columns=["URL"])
                        csv_data = df_links.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Links as CSV",
                            data=csv_data,
                            file_name="extracted_seller_links.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("No product links were found on that page. Amazon might have blocked the request or the page structure is different.")
                        
                except Exception as e:
                    st.error(f"An error occurred: {e}")

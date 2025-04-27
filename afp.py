import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import pytz
import pandas as pd

# IST timezone
IST = pytz.timezone('Asia/Kolkata')

def format_ist(timestamp: int) -> str:
    # convert UTC timestamp to IST and format as DD/MM/YYYY HH:MM:SS
    dt_ist = datetime.fromtimestamp(timestamp, IST)
    return dt_ist.strftime("%d/%m/%Y %H:%M:%S")

st.set_page_config(page_title="Facebook Reel & Video Scraper", layout="wide")
st.title("📊 Facebook Reel & Video Play & Time Scraper")

# --- Helper: recursively search for a key in nested data ---
def recursive_search_for_key(data, target_key):
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for value in data.values():
            result = recursive_search_for_key(value, target_key)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = recursive_search_for_key(item, target_key)
            if result is not None:
                return result
    return None

# --- Extract publish/create time from embedded JSON ---
def extract_publish_time(soup):
    scripts = soup.find_all("script", {"type": "application/json", "data-sjs": True})
    for script in scripts:
        try:
            data = json.loads(script.string or "{}")
            for key in ("publish_time", "creation_time"):
                val = recursive_search_for_key(data, key)
                if val:
                    try:
                        return format_ist(int(val))
                    except:
                        return str(val)
        except:
            continue
    return None

# --- Metadata extractor using requests ---
def get_fb_metadata(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Will raise an HTTPError for bad responses
    except requests.exceptions.RequestException as e:
        return {"URL": url, "Error": str(e)}

    html = response.text

    # upload time via data-utime
    upload_time = None
    match = re.search(r'itemprop="datePublished" content="(\d+)"', html)
    if match:
        upload_time = format_ist(int(match.group(1)))

    # fallback JSON for publish/create time
    soup = BeautifulSoup(html, 'html.parser')
    publish_time = extract_publish_time(soup)
    if not upload_time:
        upload_time = publish_time

    # play count
    match = re.search(r'"play_count"\s*:\s*(\d+)', html)
    play_count = int(match.group(1)) if match else None

    return {"URL": url, "Upload Time (IST)": upload_time, "Publish Time (IST)": publish_time, "Play Count": play_count}

# --- Streamlit UI Input ---
st.subheader("Enter Facebook Reel or Video URLs (one per line):")
urls_input = st.text_area("URLs:")

if st.button("🚀 Start Scraping"):
    urls = [u for u in urls_input.splitlines() if u.strip()]
    if not urls:
        st.error("Please enter at least one URL.")
    else:
        progress_bar = st.progress(0)
        status = st.empty()
        count = {'done': 0}
        total = len(urls)
        def update_progress():
            count['done'] += 1
            pct = count['done'] / total
            progress_bar.progress(pct)
            status.text(f"Scraping: {int(pct * 100)}%")

        with st.spinner("Scraping..."):
            results = []
            try:
                for url in urls:
                    result = get_fb_metadata(url.strip())
                    results.append(result)
                    update_progress()
                
                st.success("✅ All done!")
                df = pd.DataFrame(results)
                st.subheader("Results Table")
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="fb_data_ist.csv",
                    mime="text/csv"
                )
            except Exception as e:
                st.error(f"Error: {e}")

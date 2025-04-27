import streamlit as st
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import pytz
import pandas as pd
import subprocess
import os

# Ensure Playwright is installed when the app runs
if not os.path.exists('/home/appuser/.cache/ms-playwright'):
    subprocess.run(["python3", "install_playwright.py"], check=True)

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

# --- Async Reel metadata & play count extractor ---
async def get_fb_metadata_async(browser, url):
    page = await browser.new_page()
    try:
        await page.goto(url, timeout=60000)
    except PlaywrightTimeoutError:
        await page.close()
        return {"URL": url, "Upload Time (IST)": None, "Publish Time (IST)": None, "Play Count": None, "Error": "Timeout"}

    await page.wait_for_timeout(5000)
    html = await page.content()

    # upload time via data-utime
    upload_time = None
    try:
        utime = await page.locator("abbr[data-utime]").first.get_attribute("data-utime", timeout=3000)
        if utime:
            upload_time = format_ist(int(utime))
    except:
        pass

    # fallback JSON for publish/create time
    soup = BeautifulSoup(html, 'html.parser')
    publish_time = extract_publish_time(soup)
    if not upload_time:
        upload_time = publish_time

    # play count
    match = re.search(r'"play_count"\s*:\s*(\d+)', html)
    play_count = int(match.group(1)) if match else None

    await page.close()
    return {"URL": url, "Upload Time (IST)": upload_time, "Publish Time (IST)": publish_time, "Play Count": play_count}

# --- Runner for all URLs ---
CONCURRENT_LIMIT = 5
async def runner(urls, progress_callback):
    sem = asyncio.Semaphore(CONCURRENT_LIMIT)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        tasks = []
        total = len(urls)
        for url in urls:
            task = asyncio.create_task(get_fb_metadata_async(browser, url.strip()))
            task.add_done_callback(lambda _: progress_callback())
            tasks.append(task)
        results = await asyncio.gather(*tasks)
        await browser.close()
    return results

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
            try:
                results = asyncio.run(runner(urls, update_progress))
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

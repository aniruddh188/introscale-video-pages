import pandas as pd
from bs4 import BeautifulSoup
import json
import time
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

# --- Configuration ---
JSON_OUTPUT_PATH = 'netlify/functions/videos.json'
WORKSHEET_NAME = "Sheet1"

def setup_driver():
    """Initializes the Selenium WebDriver for a GitHub Actions environment."""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--log-level=3')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        driver = webdriver.Chrome(options=options)
        return driver
    except WebDriverException as e:
        print(f"--- SELENIUM ERROR ---\n{e}\nCould not initialize Chrome Driver.")
        return None

def scrape_website_url(driver, url):
    """Visits a Repliq page and scrapes the website URL."""
    try:
        driver.get(url)
        time.sleep(3) # Wait for the page to load
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if not script_tag:
            print("  - Error: Could not find the __NEXT_DATA__ script tag.")
            return "Website Not Found"

        page_data = json.loads(script_tag.string)
        website_url = page_data.get('props', {}).get('pageProps', {}).get('pageData', {}).get('result', [{}])[0].get('websiteUrl')

        if website_url:
            print(f"  - Success! Found website URL: {website_url}")
            return website_url

        print("  - Error: Could not find websiteUrl in the page data.")
        return "Website Not Found"
    except Exception as e:
        print(f"  - An unexpected error occurred during scraping: {e}")
        return "Website Not Found"

def main():
    """Main function to sync with Google Sheets, scrape, and write back."""
    print("\n--- Connecting to Google Sheets ---")
    try:
        gcp_sa_key = os.environ['GCP_SA_KEY']
        sheet_id = os.environ['GOOGLE_SHEET_ID']
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_json = json.loads(gcp_sa_key)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).worksheet(WORKSHEET_NAME)
        print("✅ Successfully connected to Google Sheets.")
    except Exception as e:
        print(f"❌ Error connecting to Google Sheets: {e}")
        return

    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    print(f"Read {len(df)} rows from the sheet.")

    print("\n--- Starting to Scrape Website URLs ---")
    driver = setup_driver()
    if not driver: return

    videos_data = {}
    for index, row in df.iterrows():
        repliq_link = row.get('Repliq Link')
        final_video_link = row.get('Final Video Link')
        company_name = row.get('CName')

        if not repliq_link or not final_video_link or not company_name:
            continue

        # --- CHANGE: Use the ID from the Repliq link ---
        video_id = str(repliq_link).split('/')[-1]
        print(f"  - Prospect: {company_name} ({video_id})")

        website_url = scrape_website_url(driver, repliq_link)

        videos_data[video_id] = {
            "prospectName": str(company_name),
            "finalVideoUrl": final_video_link,
            "websiteUrl": website_url
        }
    
    driver.quit()

    os.makedirs(os.path.dirname(JSON_OUTPUT_PATH), exist_ok=True)
    with open(JSON_OUTPUT_PATH, 'w') as f:
        json.dump(videos_data, f, indent=2)
    print(f"\nSuccessfully created '{JSON_OUTPUT_PATH}' with {len(videos_data)} entries.")
    
    final_links = []
    for index, row in df.iterrows():
        # --- CHANGE: Use the Repliq link to generate the final URL ---
        repliq_link = row.get('Repliq Link')
        if repliq_link and isinstance(repliq_link, str):
            video_id = repliq_link.split('/')[-1]
            if video_id in videos_data:
                final_links.append(f"https://video.introscale.com/{video_id}")
            else:
                final_links.append(row.get('Final Link', ''))
        else:
            final_links.append("")
    
    df['Final Link'] = final_links
    
    try:
        df_cleaned = df.fillna('')
        sheet.update([df_cleaned.columns.values.tolist()] + df_cleaned.values.tolist())
        print("✅ Successfully updated Google Sheet with new data.")
    except Exception as e:
        print(f"❌ Error writing back to Google Sheets: {e}")

    print("\n--- Automation Complete ---")

if __name__ == "__main__":
    main()

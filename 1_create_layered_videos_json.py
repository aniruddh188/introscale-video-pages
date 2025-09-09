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
# The name of the worksheet within your Google Sheet (e.g., "Sheet1")
WORKSHEET_NAME = "Sheet1"

def setup_driver():
    """Initializes the Selenium WebDriver for a GitHub Actions environment."""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless') # Must run headless in GitHub Actions
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--log-level=3')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        driver = webdriver.Chrome(options=options)
        return driver
    except WebDriverException as e:
        print(f"--- SELENIUM ERROR ---\n{e}\nCould not initialize Chrome Driver.")
        return None

def scrape_thumbnail_link(driver, url):
    """Visits a page and scrapes the required GIF thumbnail link."""
    try:
        driver.get(url)
        time.sleep(3) # A brief wait for the page's initial data to be stable
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if not script_tag:
            print("  - Error: Could not find the __NEXT_DATA__ script tag.")
            return None

        page_data = json.loads(script_tag.string)
        result_data = page_data['props']['pageProps']['pageData']['result'][0]

        # Extract the thumbnail URL from the JSON data
        thumb_url = result_data.get('previewImgOrGifUrl')

        if thumb_url:
            print("  - Success! Found the thumbnail link.")
            return thumb_url

        print("  - Error: Missing the thumbnail link in the page data.")
        return None
    except Exception as e:
        print(f"  - An unexpected error occurred during scraping: {e}")
        return None

def main():
    """Main function to sync with Google Sheets, scrape, and write back."""
    # --- Authenticate with Google Sheets using secrets ---
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

    # --- Read data from Google Sheet ---
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    print(f"Read {len(df)} rows from the sheet.")

    # --- Scrape Thumbnail Links ---
    print("\n--- Starting to Scrape Thumbnail Links ---")
    driver = setup_driver()
    if not driver: return

    videos_data = {}
    for index, row in df.iterrows():
        repliq_link = row.get('Repliq Link')
        final_video_link = row.get('Final Video Link')
        company_name = row.get('CName')

        if not repliq_link or not final_video_link or not company_name or not str(repliq_link).startswith('http'):
            continue

        video_id = str(final_video_link).split('/')[-1]
        print(f"  - Prospect: {company_name} ({video_id})")

        thumb_url = scrape_thumbnail_link(driver, repliq_link)

        if thumb_url:
            videos_data[video_id] = {
                "prospectName": str(company_name),
                "finalVideoUrl": final_video_link,
                "thumbnailUrl": thumb_url
            }
        else:
            print(f"  - WARNING: Could not get data for {company_name}. Skipping.")

    driver.quit()

    # --- Create videos.json for Netlify ---
    os.makedirs(os.path.dirname(JSON_OUTPUT_PATH), exist_ok=True)
    with open(JSON_OUTPUT_PATH, 'w') as f:
        json.dump(videos_data, f, indent=2)
    print(f"\nSuccessfully created '{JSON_OUTPUT_PATH}' with {len(videos_data)} entries.")

    # --- Update DataFrame with final links ---
    print("\n--- Preparing to update Google Sheet ---")
    final_links = []
    for index, row in df.iterrows():
        final_video_link = row.get('Final Video Link')
        if final_video_link and isinstance(final_video_link, str):
            video_id = final_video_link.split('/')[-1]
            if video_id in videos_data:
                final_links.append(f"https://video.introscale.com/{video_id}")
            else:
                final_links.append(row.get('Final Link', '')) # Preserve old link if scraping failed
        else:
            final_links.append("")

    df['Final Link'] = final_links

    # --- Write updated data back to Google Sheet ---
    try:
        # Convert NaN to empty strings for Google Sheets
        df_cleaned = df.fillna('')
        sheet.update([df_cleaned.columns.values.tolist()] + df_cleaned.values.tolist())
        print("✅ Successfully updated Google Sheet with new data.")
    except Exception as e:
        print(f"❌ Error writing back to Google Sheets: {e}")

    print("\n--- Automation Complete ---")

if __name__ == "__main__":
    main()

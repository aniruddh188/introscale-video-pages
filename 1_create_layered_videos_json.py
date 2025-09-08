import pandas as pd
from bs4 import BeautifulSoup
import json
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

# --- Configuration ---
CSV_FILE_PATH = 'RepliQ results.csv'
JSON_OUTPUT_PATH = 'videos.json' 

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

def scrape_video_links(driver, url):
    """
    Visits a page and scrapes the screen video, face video, and thumbnail URLs.
    """
    try:
        driver.get(url)
        time.sleep(3) # A brief wait for the page's initial data to be stable
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if not script_tag:
            print("  - Error: Could not find the __NEXT_DATA__ script tag.")
            return None, None, None

        page_data = json.loads(script_tag.string)
        result_data = page_data['props']['pageProps']['pageData']['result'][0]
        
        screen_video_url = result_data.get('imgUrl')
        face_video_url = result_data.get('selectedVideo')
        thumbnail_url = result_data.get('previewImgOrGifUrl')
        
        if screen_video_url and face_video_url and thumbnail_url:
            print("  - Success! Found all three required links.")
            return screen_video_url, face_video_url, thumbnail_url
        else:
            print("  - Error: Missing one or more required links in the page data.")
            return None, None, None

    except Exception as e:
        print(f"  - An unexpected error occurred during scraping: {e}")
        return None, None, None

def main():
    """Main function to control the scraping and CSV update process."""
    if os.path.exists(JSON_OUTPUT_PATH):
        os.remove(JSON_OUTPUT_PATH)
    
    try:
        df = pd.read_csv(CSV_FILE_PATH)
    except FileNotFoundError:
        print(f"Error: The file '{CSV_FILE_PATH}' was not found.")
        return

    print("\n--- Starting to Scrape Video Links for Netlify ---")
    driver = setup_driver()
    if not driver: return

    videos_data = {}
    
    for index, row in df.iterrows():
        print(f"\n--- Processing Row {index} ---")
        page_url = row.get('Video link')
        company_name = row.get('CName')
        
        if pd.isna(page_url) or pd.isna(company_name):
            continue

        video_id = page_url.split('/')[-1]
        prospect_name = str(company_name).strip()
        
        print(f"  - Prospect: {prospect_name} ({video_id})")
        
        screen_url, face_url, thumb_url = scrape_video_links(driver, page_url)

        if screen_url and face_url and thumb_url:
            videos_data[video_id] = { 
                "prospectName": prospect_name, 
                "screenVideoUrl": screen_url, 
                "faceVideoUrl": face_url,
                "thumbnailUrl": thumb_url 
            }
            print(f"  - Data added successfully.")
        else:
            print(f"  - Warning: Could not get all data for this entry. Skipping.")

    driver.quit()

    with open(JSON_OUTPUT_PATH, 'w') as f:
        json.dump(videos_data, f, indent=2)

    print(f"\nSuccessfully created '{JSON_OUTPUT_PATH}' with {len(videos_data)} entries.")

    # --- Update the original CSV with the final links ---
    print("\n--- Updating CSV with final introscale.com links ---")
    try:
        final_links = []
        for index, row in df.iterrows():
            page_url = row.get('Video link')
            if pd.notna(page_url):
                video_id = page_url.split('/')[-1]
                if video_id in videos_data:
                    final_links.append(f"https://video.introscale.com/{video_id}")
                else:
                    final_links.append("") # Leave blank if scraping failed
            else:
                final_links.append("")

        df['Final Link'] = final_links
        df.to_csv(CSV_FILE_PATH, index=False)
        print(f"✅ Successfully updated '{CSV_FILE_PATH}' with a new 'Final Link' column.")
    except Exception as e:
        print(f"  - Warning: Could not update the CSV file. Error: {e}")

    print("\nChanges will now be committed back to the repository.")

if __name__ == "__main__":
    main()


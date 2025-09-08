import pandas as pd
from bs4 import BeautifulSoup
import json
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

# --- Configuration ---
CSV_FILE_PATH = 'RepliQ_results.csv'
# --- FIX: Set the output path to the correct folder for Netlify ---
JSON_OUTPUT_PATH = 'netlify/functions/videos.json' 

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

def scrape_video_links(driver, url):
    """
    Visits a page and scrapes the screen video, face video, and thumbnail URLs.
    """
    try:
        driver.get(url)
        time.sleep(3) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if not script_tag:
            return None, None, None

        page_data = json.loads(script_tag.string)
        result_data = page_data['props']['pageProps']['pageData']['result'][0]
        
        screen_video_url = result_data.get('imgUrl')
        face_video_url = result_data.get('selectedVideo')
        thumbnail_url = result_data.get('previewImgOrGifUrl')
        
        if screen_video_url and face_video_url and thumbnail_url:
            return screen_video_url, face_video_url, thumbnail_url
        else:
            return None, None, None

    except Exception:
        return None, None, None

def main():
    """Main function to control the scraping and CSV update process."""
    # Ensure the target directory exists before trying to save the file
    if os.path.exists(JSON_OUTPUT_PATH):
        os.remove(JSON_OUTPUT_PATH)
    os.makedirs(os.path.dirname(JSON_OUTPUT_PATH), exist_ok=True)
    
    try:
        df = pd.read_csv(CSV_FILE_PATH, engine='python')
    except FileNotFoundError:
        print(f"Error: The file '{CSV_FILE_PATH}' was not found.")
        return

    print("\n--- Starting to Scrape Video Links for Netlify ---")
    driver = setup_driver()
    if not driver: return

    videos_data = {}
    
    for index, row in df.iterrows():
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
        else:
            print(f"  - WARNING: Could not get data for {prospect_name}. Skipping.")

    driver.quit()

    with open(JSON_OUTPUT_PATH, 'w') as f:
        json.dump(videos_data, f, indent=2)

    print(f"\nSuccessfully created '{JSON_OUTPUT_PATH}' with {len(videos_data)} entries.")

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
                    # Preserve existing link if scraping failed
                    final_links.append(row.get('Final Link', ''))
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


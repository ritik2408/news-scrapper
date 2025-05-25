import requests
from bs4 import BeautifulSoup
import json
import logging
import time
import smtplib
from email.mime.text import MIMEText
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

EMAIL_SENDER = "shivamy4020@gmail.com"  
EMAIL_PASSWORD = "bkps quko algb lwul"   
EMAIL_RECEIVER = "shivam.yadav@collegedunia.com"  
SMTP_SERVER = "smtp.gmail.com"       
SMTP_PORT = 587                       


WEBSITE_URL = "https://www.shiksha.com/news/exams/" 
BASE_URL = "https://www.shiksha.com/"  # Base URL for absolute URLs
ARTICLE_FILE = "seen_articles_shiksha.json"  # File to store seen articles

def load_seen_articles():
    """Load previously seen articles from JSON file."""
    try:
        with open(ARTICLE_FILE, 'r') as f:
            return set(tuple(item) for item in json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_seen_articles(articles):
    """Save seen articles to JSON file."""
    with open(ARTICLE_FILE, 'w') as f:
        json.dump(list(articles), f)

def send_email(subject, body):
    """Send an email with the given subject and body."""
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        logging.info(f"Email sent: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def scrape_articles(url):
    """Scrape articles and return new ones."""
    start_time = time.time()
    logging.info(f"Scraping {url}")

    try:
        # Define headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Referer': 'https://www.shiksha.com/',
            'Accept-Encoding': 'gzip, deflate',
            'Upgrade-Insecure-Requests': '1'
        }

        # Set up session with retries
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))

        # Send HTTP request with timeout
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        logging.info(f"Page fetched in {time.time() - start_time:.2f} seconds")

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all article cards based on the HTML structure you provided
        article_cards = soup.find_all('div', class_='articleCard_Wrapper')
        if not article_cards:
            logging.warning("No articles found with class 'articleCard_Wrapper'")
            return []

        logging.info(f"Found {len(article_cards)} articles")

        # Load seen articles
        seen_articles = load_seen_articles()
        new_articles = []

        # Process each article card (limit to 20)
        for i, article in enumerate(article_cards[:20]):
            try:
                # Find the article title and URL within the articleTitle h3 tag
                title_section = article.find('h3', class_='articleTitle')
                if not title_section:
                    continue
                
                # Find the link within the title section
                link_elem = title_section.find('a')
                if not link_elem:
                    continue
                
                # Extract title text (remove LIVE indicators and clean up)
                title = link_elem.get_text().strip()
                # Remove "LIVE" text if present
                title = title.replace('LIVE', '').strip()
                
                # Extract URL
                url_path = link_elem.get('href', '')
                if not url_path:
                    continue
                
                # Ensure URL is absolute
                if url_path.startswith('/'):
                    full_url = BASE_URL.rstrip('/') + url_path
                elif url_path.startswith('http'):
                    full_url = url_path
                else:
                    full_url = BASE_URL.rstrip('/') + '/' + url_path
                
                # Extract author and date information if available
                author_info = article.find('div', class_='authorInfo')
                author = 'N/A'
                date = 'N/A'
                
                if author_info:
                    author_link = author_info.find('a')
                    if author_link:
                        author = author_link.get_text().strip()
                    
                    date_elem = author_info.find('strong', class_='articelUpdatedDate')
                    if date_elem:
                        date = date_elem.get_text().strip()
                
                # Create article tuple with additional info
                article_tuple = (title, full_url, author, date)
                
                # Check if this is a new article
                simple_tuple = (title, full_url)  # For backward compatibility
                if simple_tuple not in seen_articles and title and full_url:
                    new_articles.append(article_tuple)
                    logging.info(f"New article found: {title[:60]}...")
                
            except Exception as e:
                logging.error(f"Error processing article {i}: {e}")
                continue

        # Update seen articles (convert back to simple tuples for storage)
        simple_tuples = [(title, url, author, date)[:2] for title, url, author, date in new_articles]
        seen_articles.update(simple_tuples)
        save_seen_articles(seen_articles)

        return new_articles

    except requests.Timeout:
        logging.error("Request timed out after 20 seconds")
        return []
    except requests.RequestException as e:
        logging.error(f"Error fetching URL: {e}")
        return []
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return []

def main():
    """Run the scraper once - suitable for GitHub Actions scheduling."""
    logging.info("Starting Shiksha news monitoring script")
    
    try:
        new_articles = scrape_articles(WEBSITE_URL)

        for article_info in new_articles:
            title, url, author, date = article_info

            subject = f"New Shiksha Article: {title[:50]}..."
            body = f"""New article found on Shiksha.com:

Title: {title}
Author: {author}
Date: {date}
URL: {url}

---
Shiksha News Monitor"""

            send_email(subject, body)

        if new_articles:
            logging.info(f"Sent {len(new_articles)} email(s) for new articles")
        else:
            logging.info("No new articles found")
            
        logging.info("Script completed successfully")
            
    except Exception as e:
        logging.error(f"Error during execution: {e}")
        raise  # Re-raise to make GitHub Actions aware of the failure

if __name__ == "__main__":
    main()
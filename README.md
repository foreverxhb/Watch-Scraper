# Watch-Scraper
Python script to scrape product information from the first page of a Flipkart search result for watches.



# Objective

This project is a Python web scraping script that extracts product information for watches from the first page of a Flipkart search result. The focus is on watches priced under ₹2000.

# Features

Fetches HTML content of Flipkart search results.

Saves raw HTML content in a .txt file.

Extracts the following details for each watch:

Watch Name

Brand (parsed from the name)

Price

Availability (if available)

Filters out watches priced above ₹2000.

Stores the extracted data in an Excel file.

# Tech Stack

Python 3

Libraries used:

requests / urllib → Fetching HTML

BeautifulSoup → Parsing HTML

pandas / openpyxl → Exporting to Excel

# How to Run

Clone the repository:

git clone https://github.com/foreverxhb/watch-scraper.git
cd watch-scraper


Install dependencies:

pip install -r requirements.txt


Run the script:

python watch_scraper.py


Output:

page_content.txt → Raw HTML content.

watches.xlsx → Extracted product data.

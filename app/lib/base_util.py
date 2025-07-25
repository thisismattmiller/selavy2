
import json
import os
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Union, Optional

def query_semlab(query_value: str) -> List[Dict[str, Optional[str]]]:
    """
    Queries the Semlab base search engine and parses the HTML results.

    This function takes a search query, retrieves the search results page
    from base.semlab.io, and parses the HTML to extract the label, QID,
    and description for each result.

    Args:
        query_value: The string to search for on Semlab.

    Returns:
        A list of dictionaries. Each dictionary represents a search result
        and contains the following keys:
        - 'label' (str): The main label of the item.
        - 'qid' (str): The unique QID of the item.
        - 'description' (str or None): The description of the item, if it exists.
        Returns an empty list if the request fails or no results are found.
    """
    base_url = "https://base.semlab.io/w/index.php"
    params = {"search": query_value}

    try:
        # Make the request with a user-agent to appear as a standard browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(base_url, params=params, headers=headers)
        # Raise an exception if the request returned an unsuccessful status code (4xx or 5xx)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the web request: {e}")
        return False

    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all list items that correspond to a search result
    search_results_html = soup.find_all('li', class_='mw-search-result')
    
    parsed_results = []

    for item in search_results_html:
        # The label and qid are guaranteed to exist per the requirements
        label_tag = item.find('span', class_='wb-itemlink-label')
        qid_tag = item.find('span', class_='wb-itemlink-id')

        # As a safeguard, skip if the core elements aren't found
        if not label_tag or not qid_tag:
            continue

        # Extract the text and clean it up
        label = label_tag.get_text(strip=True)
        # The qid text is like "(Q29020)", so we strip the parentheses
        qid = qid_tag.get_text(strip=True).strip('()')

        # The description is optional, so we must handle cases where it's not present
        description_tag = item.find('span', class_='wb-itemlink-description')
        description = None  # Default to None if not found
        if description_tag:
            description = description_tag.get_text(strip=True)

        # Append the structured data to our results list
        parsed_results.append({
            'label': label,
            'qid': qid,
            'description': description,
            'order': None
        })
    print(f"Parsed result: {parsed_results}")
    return parsed_results



def search_base(query):
    """
    Search for a query in the SemLab knowledge base.

    Args:
        query (str): The query string to search for.

    Returns:
        list: A list of search results, where each result is a dictionary
              containing 'label', 'qid', and 'description' keys.
    """
    # Call the query_semlab function to perform the search
    results = query_semlab(query)
    return results

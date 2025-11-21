
import json
import os
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Union, Optional



import re
import json
import os
import requests
from wikibaseintegrator import WikibaseIntegrator

from wikibaseintegrator.datatypes import Item
from wikibaseintegrator.datatypes import String
from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_login import LoginError




def wikibase_mint_entity(user_data, entity, user_store, request_sid):
    try:
        login_instance = user_data['login_instance']
        login_token = user_data['login_token']
        wbi = WikibaseIntegrator(login=login_instance)

        # Extract mintData from the entity
        mint_data = entity['entity'].get('mintData', {})

        # Create a new item
        new_item = wbi.item.new()

        # Set label (authLabel)
        if mint_data.get('authLabel'):
            new_item.labels.set('en', mint_data['authLabel'])

        # Set description
        if mint_data.get('description'):
            new_item.descriptions.set('en', mint_data['description'])

        # Set aliases (variantLabel, removing any nulls)
        if mint_data.get('variantLabel'):
            variant_labels = [label for label in mint_data['variantLabel'] if label is not None]
            for label in variant_labels:
                new_item.aliases.set('en', label)

        # Add claims
        # P8: Wikidata QID (identifier)
        if mint_data.get('wikidataQid') and mint_data['wikidataQid'].strip():
            claim_p8 = String(prop_nr='P8', value=mint_data['wikidataQid'])
            new_item.claims.add(claim_p8)

        # P1: instanceOf (list of QIDs)
        if mint_data.get('instanceOf'):
            instance_of_list = mint_data['instanceOf']
            if not isinstance(instance_of_list, list):
                instance_of_list = [instance_of_list]
            # Filter out None and empty string values
            instance_of_list = [qid for qid in instance_of_list if qid and str(qid).strip()]
            if instance_of_list:
                p1_claims = [Item(prop_nr='P1', value=qid) for qid in instance_of_list]
                new_item.claims.add(p1_claims)

        # P11: project (list of QIDs)
        if mint_data.get('project'):
            project_list = mint_data['project']
            if not isinstance(project_list, list):
                project_list = [project_list]
            # Filter out None and empty string values
            project_list = [qid for qid in project_list if qid and str(qid).strip()]
            if project_list:
                p11_claims = [Item(prop_nr='P11', value=qid) for qid in project_list]
                new_item.claims.add(p11_claims)

        # Write the new item to the wikibase
        result = new_item.write()

        # Return JSON serializable response with the QID
        return {'success': True, 'qid': result.id}

    except LoginError as e:
        # Try to re-login if login failed
        print(f'Login failed, attempting to re-login: {e}', flush=True)

        if 'login_data' in user_data:
            login_data = user_data['login_data']

            try:
                # Re-create login instance
                new_login_instance = wbi_login.Clientlogin(
                    user=login_data['username'],
                    password=login_data['password']
                )

                # Update user_store with new login instance
                import uuid
                new_login_token = str(uuid.uuid4())
                user_store[request_sid] = {
                    'login_instance': new_login_instance,
                    'login_data': login_data,
                    'login_token': new_login_token
                }

                # Retry the minting with new login
                wbi = WikibaseIntegrator(login=new_login_instance)
                mint_data = entity['entity'].get('mintData', {})
                new_item = wbi.item.new()

                if mint_data.get('authLabel'):
                    new_item.labels.set('en', mint_data['authLabel'])

                if mint_data.get('description'):
                    new_item.descriptions.set('en', mint_data['description'])

                if mint_data.get('variantLabel'):
                    variant_labels = [label for label in mint_data['variantLabel'] if label is not None]
                    for label in variant_labels:
                        new_item.aliases.set('en', label)

                if mint_data.get('wikidataQid') and mint_data['wikidataQid'].strip():
                    claim_p8 = String(prop_nr='P8', value=mint_data['wikidataQid'])
                    new_item.claims.add(claim_p8)

                if mint_data.get('instanceOf'):
                    instance_of_list = mint_data['instanceOf']
                    if not isinstance(instance_of_list, list):
                        instance_of_list = [instance_of_list]
                    instance_of_list = [qid for qid in instance_of_list if qid and str(qid).strip()]
                    if instance_of_list:
                        p1_claims = [Item(prop_nr='P1', value=qid) for qid in instance_of_list]
                        new_item.claims.add(p1_claims)

                if mint_data.get('project'):
                    project_list = mint_data['project']
                    if not isinstance(project_list, list):
                        project_list = [project_list]
                    project_list = [qid for qid in project_list if qid and str(qid).strip()]
                    if project_list:
                        p11_claims = [Item(prop_nr='P11', value=qid) for qid in project_list]
                        new_item.claims.add(p11_claims)

                result = new_item.write()
                return {'success': True, 'qid': result.id}

            except Exception as retry_error:
                return {'success': False, 'error': f'Re-login attempt failed: {str(retry_error)}'}
        else:
            return {'success': False, 'error': f'Login failed and no credentials available: {str(e)}'}

    except Exception as e:
        return {'success': False, 'error': str(e)}
    

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
    print(response.text)
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

import re
import json
import os
import requests

SPARQL_ENDPOINT = "https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql"
CLASS_QID = "Q19063"



def split_blocks(text):
	"""
	Splits the text into blocks based on the <BLOCKBREAK/> tag.
	:param text: The text to process.
	:return: A list of blocks.
	"""
	blocks = text.split("<BLOCKBREAK/>")
	results = {}

	pattern = r"\{[^|}]+\|[^|}]+\|[^|}]+\}"


	for i in range(len(blocks)):
		results[i] = {}
		results[i]['markup'] = blocks[i].strip()


		text = results[i]['markup']
		matches = re.findall(pattern, text)		

		for match in matches:
			word = match.split("|")[0][1:]
			text = text.replace(match, word)
		
		results[i]['clean'] = text





	return results


def extract_entities(blocks):
	"""
	Extracts entities from the text.
	:param text: The text to process.
	:return: A list of entities.
	"""
	pattern = r"\{[^|}]+\|[^|}]+\|[^|}]+\}"

	entities = {}

	for block in blocks:
			

		matches = re.findall(pattern, blocks[block]['markup'])

		for match in matches:
			entity = match.split("|")[0][1:]
			entity = entity.replace("-\n", "")
			entity = entity.replace("\n", "")

			entity_type = match.split("|")[2][:-1]
			entity_id = match.split("|")[1]
			if entity_id not in entities:
				entities[entity_id] = {
					"entity": entity,
					"type": entity_type,
					"internal_id": entity_id,
					"labels": [entity],
					"blocks": [block], 
					"count": 1,
				}
			else:
				if block not in entities[entity_id]['blocks']:
					entities[entity_id]['blocks'].append(block)

				entities[entity_id]['count'] += 1
				if entity not in entities[entity_id]['labels']:
					entities[entity_id]['labels'].append(entity)


			# entities.append((entity, entity_type))

	return entities

def align_types(entities):
	# get all the X entitie types
	sparql = """
		SELECT ?item ?itemLabel 
		WHERE 
		{
		?item  wdt:P1 wd:Q19063.
		SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
		}
	""".replace("wd:Q19063", f"wd:{CLASS_QID}")
	print("sparql: ", sparql, flush=True)
	headers = {
		'Accept': 'application/sparql-results+json',
	}
	params = {
		'query' : sparql
	}

	try:
		response = requests.get(
			SPARQL_ENDPOINT,
			params=params,
			headers=headers,
		)
		response.raise_for_status()
		data = response.json()

	except requests.exceptions.RequestException as e:
		print(f"An error occurred while making the SPARQL request: {e}",flush=True)
		return {}
	print("data: ", data, flush=True)
	lookup = {}

	for result in data['results']['bindings']:
		print(result, flush=True)
		qid = result['item']['value'].split("/")[-1]
		label = result['itemLabel']['value']
		lookup[qid] = {
			"label": label,
			"qid": qid,
			"matching_doc_types": [],
		}


	
	doc_types_list = []
	for entity_id in entities:
		print(entities[entity_id],flush=True)
		if entities[entity_id]['type'] not in doc_types_list:
			doc_types_list.append(entities[entity_id]['type'])
		
	
	print("lookup: ", lookup, flush=True)
	print("doc_types_list: ", "\n".join(doc_types_list), flush=True)

	prompt = f"""
	You are a helpful assistant who is aligning entity types from two different systems.
	This is a list of entity types from the first system:
	{doc_types_list}
	The next text is a JSON object with a list of entity types from the second system.
	compare the two lists (the list above and the value in each "label" key in the JSON object) 
	try to match the system 1 type to the best system two type. If you find a good match the system 2 type to the "matching_doc_types" key array.
	Return the modified JSON object with the "matching_doc_types" key array filled in.
	Here is the JSON object:
	{json.dumps(lookup, indent=2)}

	"""
	with open("/data/prompt.txt", "w") as f:
		f.write(prompt)



def build_know_label_llm_compare_prompt(entities, wikibase_type, doc_type):


	# get all the X entitie types
	sparql = """
		SELECT ?item ?itemLabel ?project ?projectLabel
		WHERE 
		{
		?item  wdt:P1 wd:Q1.
		OPTIONAL{
		?item wdt:P11 ?project.
			}
		SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
		}
	""".replace("wd:Q1", f"wd:{wikibase_type}")
	
	headers = {
		'Accept': 'application/sparql-results+json',
	}
	params = {
		'query' : sparql
	}

	try:
		response = requests.get(
			SPARQL_ENDPOINT,
			params=params,
			headers=headers,
		)
		response.raise_for_status()
		data = response.json()

	except requests.exceptions.RequestException as e:
		print(f"An error occurred while making the SPARQL request: {e}")
		return {}
	

	lookup = {}

	for result in data['results']['bindings']:
		qid = result['item']['value'].split("/")[-1]
		if qid not in lookup:
			lookup[qid] = {
				"label": result['itemLabel']['value'],
				"project": []
			}

		if 'projectLabel' in result:
			lookup[qid]['project'].append(result['projectLabel']['value'])


	for entity_id in entities:

		print(entities[entity_id],flush=True)
		longest_label = max(entities[entity_id]['labels'], key=len)


def return_ner(text):
	"""
	Returns the named entities in the text.
	:param text: The text to process.
	:return: A list of named entities.
	"""


	blocks =split_blocks(text)
	entities = extract_entities(blocks)


	# build_know_label_llm_compare_prompt(entities, "Q1")
	align_types(entities)

	results = {
		"blocks": blocks,
		"entities": entities,
	}


	return results
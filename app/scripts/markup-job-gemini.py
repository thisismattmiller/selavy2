import os
from google import genai
from google.genai import types
import json
import sys
import requests

SPARQL_ENDPOINT = "https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql"
CLASS_QID = "Q19063"

jobs_id = sys.argv[1]
user_name = sys.argv[2]

print('/data/jobs/' + jobs_id + '.json',flush=True)
job_data = json.load(open(f'/data/jobs/{user_name}/' + jobs_id + '.json'))



markup_text = job_data['text']


model = job_data.get('model', 'gemini-2.5-flash')

budget = 24576
if 'pro' in model:
    budget = 32768

rough_word_count_orginal = len(markup_text.split(' '))


client = genai.Client(
    api_key=os.environ.get("GOOGLE_GENAI"),
)


total_tokens = client.models.count_tokens(
    model=model, contents=markup_text
)

print("total_tokens: ", total_tokens)



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
    json.dump({
        "id": jobs_id,
        "status": 'LLM_MARKUP_ERROR',
        "user": job_data['user'],
        'status_percent': str(e),
        "created_at": job_data['created_at'],
        "title": job_data['title']
    },open(f'/data/jobs/{user_name}/' + jobs_id + '.meta.json','w'),indent=2)
    sys.exit(1)

classes =[]
class_map = {}

try:
    for result in data['results']['bindings']:
        qid = result['item']['value'].split("/")[-1]
        label = result['itemLabel']['value']

        if label not in ['class', 'item', 'thing', 'artwork (structural class)', 'reason for uncertainty', 'property']:

            classes.append(label)
            class_map[label] = qid
except:
    print(f"An error occurred while making the SPARQL request: {e}",flush=True)

    json.dump({
        "id": jobs_id,
        "status": 'LLM_MARKUP_ERROR',
        "user": job_data['user'],
        'status_percent': str(e),
        "created_at": job_data['created_at'],
        "title": job_data['title']
    },open(f'/data/jobs/{user_name}/' + jobs_id + '.meta.json','w'),indent=2)
    sys.exit(1)













contents = [
    types.Content(
        role="user",
        parts=[
            types.Part.from_text(text=markup_text)
        ],
    ),
]

system_instruction = """You are a helpful assistant processing text. You are identifying entities which are people, places, things, events, artworks, etc. In the following text wrap each entity in curly brackets create or reuse a unique integer identifier for each and place it inside the curly brackets separated by a pipe character with the text, also add the type of entity it is seperated by a pipe character, for example {John Doe|####|Person} where \"####\" is the unique integer identifier, and "Person" is entity type, the entity must be wrapped in the curly brackets, reuse that unique integer identifier for each occurrence of the same entity in the rest of the text. Return the full text do not modify the orgnial text. Some entities may span a line break, if they do remove the hyphen if there and remove the newline character. Do not put newline characters inside the curly brackets, remove any newline character inside the curly brackets. Return the full text, do not add any additonal text to the start of the response. 
Preference using the following entity types: """ + ", ".join(classes) + """. But if a entity does not fit you may makup a new class.                             
You also add lines to the text to seperate the document into sections. Insert the text "<BLOCKBREAK/>" to divide up the document by contextual text groupings. If the text is an article group the pharagraphs together based on context. For example several pharagraphs could cover one idea or topic, group those together with one "<BLOCKBREAK/>" after all of the relevant pharagraphs.  If the text is a interview group the text by by question and answer groupings. If the text is a diary group the text based on dates. Here is the text:"""

print(system_instruction,flush=True)
generate_content_config = types.GenerateContentConfig(
    temperature=0,
    thinking_config = types.ThinkingConfig(
        thinking_budget=budget,
    ),
    response_mime_type="text/plain",
    system_instruction=[
        types.Part.from_text(text=system_instruction),
    ],
)

print(markup_text,flush=True)


response_text = ""
chunk_count = 0
last_percent_done = 0
print("streaming",flush=True)
for chunk in client.models.generate_content_stream(
    model=model,
    contents=contents,
    config=generate_content_config,
):
    print(chunk.text, end="",flush=True)

    if chunk != None and chunk.text != None and chunk.text.strip() != "":
        response_text=response_text+chunk.text
        chunk_count=chunk_count+1
        if chunk_count>5:
            job_data['text_markup'] = response_text
            rough_word_count_markup = len(response_text.split(' '))
            job_data["status"] = "LLM_MARKING_UP",
            job_data['status_percent'] = f"{rough_word_count_markup}/{rough_word_count_orginal} ({int(rough_word_count_markup/rough_word_count_orginal*100)}%)"
            last_percent_done = int(rough_word_count_markup/rough_word_count_orginal*100)
            json.dump(job_data,open(f'/data/jobs/{user_name}/' + jobs_id + '.json','w'),indent=2)
            chunk_count=0
            print(job_data['status_percent'],flush=True)

            json.dump({
                "id": jobs_id,
                "status": 'LLM_MARKING_UP',
                "user": job_data['user'],
                'status_percent': job_data['status_percent'],
                "created_at": job_data['created_at'],
                "title": job_data['title']
            },open(f'/data/jobs/{user_name}/' + jobs_id + '.meta.json','w'),indent=2)



job_data["status"] = "LLM_MARKUP_COMPLETE",
job_data['text_markup'] = response_text
job_data['status_percent'] = "(100%)"
job_data['last_percent_done'] = last_percent_done
job_data['class_map'] = class_map

json.dump(job_data,open(f'/data/jobs/{user_name}/' + jobs_id + '.json','w'),indent=2)


json.dump({
    "id": jobs_id,
    "status": 'LLM_MARKUP_COMPLETE',
    "user": job_data['user'],
    'status_percent': job_data['status_percent'],
    "created_at": job_data['created_at'],
    "title": job_data['title']
},open(f'/data/jobs/{user_name}/' + jobs_id + '.meta.json','w'),indent=2)
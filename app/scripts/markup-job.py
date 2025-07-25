import os
import sys
import json
from openai import OpenAI


# os.environ.get('NEBIUS_API')

jobs_id = sys.argv[1]
print('/data/jobs/' + jobs_id + '.json',flush=True)
job_data = json.load(open('/data/jobs/' + jobs_id + '.json'))

markup_text = job_data['text'][0:11778]

rough_word_count_orginal = len(markup_text.split(' '))

# we are running it through the dangg machine
client = OpenAI(
    base_url="https://api.studio.nebius.ai/v1/",
    api_key=os.environ.get("NEBIUS_API"),
)   


completion = client.chat.completions.create(
    model="meta-llama/Llama-3.3-70B-Instruct",
    messages=[
        {
            "role": "system",
            "content" : """
                You are a helpful assistant processing text. You are identifying entities which are people, places, things, events, artworks, etc.
            """
        },
        {
            "role": "system",
            "content" : """
                In the following text wrap each entity in curly brackets create or reuse a unique integer identifier for each and place it inside the curly brackets separated by a pipe character with the text, also add the type of entity it is seperated by a pipe character, for example {John Doe|####|Person} where \"####\" is the unique integer identifier, and "Person" is entity type, the entity must be wrapped in the curly brackets, reuse that unique integer identifier for each occurrence of the same entity in the rest of the text. Return the full text and make no other changes to it. Some entities may span a line break. Return the full text, do not add any additonal text to the start of the response. Here is the text:
            """
        },        
        {
            "role": "user",
            "content": markup_text
        }
    ],

    temperature=0,
    max_tokens=0,
    stream=True
)

response_text = ""
chunk_count = 0
for chunk in completion:
    content = chunk.choices[0].delta.content
    response_text=response_text+content
    chunk_count=chunk_count+1
    if chunk_count>175:
        job_data['text_markup'] = response_text
        rough_word_count_markup = len(response_text.split(' '))
        job_data['status_percent'] = f"{rough_word_count_markup}/{rough_word_count_orginal} ({int(rough_word_count_markup/rough_word_count_orginal*100)}%)"
        json.dump(job_data,open('/data/jobs/' + jobs_id + '.json','w'),indent=2)
        chunk_count=0



job_data['text_markup'] = response_text
job_data['status_percent'] = f"{rough_word_count_markup}/{rough_word_count_orginal} ({int(rough_word_count_markup/rough_word_count_orginal*100)}%)"
json.dump(job_data,open('/data/jobs/' + jobs_id + '.json','w'),indent=2)





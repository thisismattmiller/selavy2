import re
import json
import os
from google import genai
from google.genai import types

GOOGLE_GEMINI_MODEL = "gemini-2.5-flash"

client = genai.Client(
	api_key=os.environ.get("GOOGLE_GENAI"),
)


def judge_diff(diff):	 
	model = "gemini-2.5-flash-preview-04-17"
	model = GOOGLE_GEMINI_MODEL

	contents = [
		types.Content(
			role="user",
			parts=[
				types.Part.from_text(text=f"""
					{diff['orginal_text']}
					{diff['processed_text']}
				"""),
			],
		),
	]
	generate_content_config = types.GenerateContentConfig(
		response_mime_type="application/json",
		system_instruction=[
			types.Part.from_text(text="""You are a helpful assistant who compares two lines of text, the first line is the original text, the second line is the modified text, there will be a word or words in-between two asterisk characters (*) that is different. You judge if the word or words different between the two asterisks significantly change the meaning of the sentence. Return JSON object with two keys \"significantChange\" set to true or false based on if the meaning is changed by the difference. If the meaning is not significantly changed by the difference, because it is a fixed typo, or formatting change, etc you return false for significantChange. Also return a key \"reason\" which explains briefly in one sentence your reasoning. Here are the two sentences:"""),
		],
	)

	results = ""
	
	for chunk in client.models.generate_content_stream(
		model=model,
		contents=contents,
		config=generate_content_config,
	):
		print(chunk.text, end="")
		try:
			results += chunk.text
		except Exception as e:
			print("Error in chunk: ", e)
			print("results: ", results)
			


	try:
		results = json.loads(results)

	except json.JSONDecodeError as e:
		results = None

	return results



def ask_llm_structured(prompt):


	model = "gemini-2.5-flash-preview-05-20"
	model = GOOGLE_GEMINI_MODEL

	contents = [
		types.Content(
			role="user",
			parts=[
				types.Part.from_text(text=f"""{prompt}"""),
			],
		),
	]
	generate_content_config = types.GenerateContentConfig(
		temperature=0,
		response_mime_type="application/json",
	)
	response_text = ""
	for chunk in client.models.generate_content_stream(
		model=model,
		contents=contents,
		config=generate_content_config,
	):	
		if chunk != None:
			if isinstance(chunk.text, str):
				response_text = response_text + chunk.text


	try:
		response_text = json.loads(response_text)
		return {'success': True, 'response': response_text}
	except json.JSONDecodeError as e:
		print("Error decoding JSON: ", e)
		response_text = None
		print("response_text: ", response_text)
		return {'success': False, 'response': None}


def ask_llm_reconcile_project_wide(prompt):

	print("Sending Proposed Project-Wide Reconciliation Prompt to LLM:", flush=True)
	model = GOOGLE_GEMINI_MODEL
	contents = [
		types.Content(
			role="user",
			parts=[
				types.Part.from_text(text=prompt),
			],
		),
	]
	generate_content_config = types.GenerateContentConfig(
		temperature=0,
		response_mime_type="application/json",
		response_schema=genai.types.Schema(
			type = genai.types.Type.ARRAY,
			items = genai.types.Schema(
				type = genai.types.Type.OBJECT,
				required = ["entity", "type", "internal_id", "qid"],
				properties = {
					"entity": genai.types.Schema(
						type = genai.types.Type.STRING,
					),
					"type": genai.types.Schema(
						type = genai.types.Type.STRING,
					),
					"internal_id": genai.types.Schema(
						type = genai.types.Type.STRING,
					),
					"qid": genai.types.Schema(
						type = genai.types.Type.STRING,
						nullable = "True",
					),


					
				},
			),
		),
	)
	print("here")
	response_text = ""
	for chunk in client.models.generate_content_stream(
		model=model,
		contents=contents,
		config=generate_content_config,
	):
		# print(".",end="", flush=True)
		# print("", flush=True)
		print(chunk.text, end="")
		if chunk.text != None:
			response_text = response_text + chunk.text

	try:
		print("Response from LLM: ", response_text, flush=True)

		response_text = json.loads(response_text)
		print("response_text: ", response_text, flush=True)
		return {'success': True, 'response': response_text}
	except json.JSONDecodeError as e:
		print("Error decoding JSON: ", e)
		return {'success': False, 'response': None}




def ask_llm_reconcile_build_search_order(prompt):

	
	print("Sending Proposed Project-Wide Reconciliation Prompt to LLM:", flush=True)
	model = GOOGLE_GEMINI_MODEL
	contents = [
		types.Content(
			role="user",
			parts=[
				types.Part.from_text(text=prompt),
			],
		),
	]
	generate_content_config = types.GenerateContentConfig(
		temperature=0,
		response_mime_type="application/json",
		response_schema=genai.types.Schema(
            type = genai.types.Type.ARRAY,
            items = genai.types.Schema(
                type = genai.types.Type.OBJECT,
                required = ["label", "description", "qid", "order"],
                properties = {
                    "label": genai.types.Schema(
                        type = genai.types.Type.STRING,
                    ),
                    "description": genai.types.Schema(
                        type = genai.types.Type.STRING,
                    ),
                    "qid": genai.types.Schema(
                        type = genai.types.Type.STRING,
                    ),
                    "order": genai.types.Schema(
                        type = genai.types.Type.INTEGER,
                    ),
                },
            ),
        ),

	)
	print("here")
	response_text = ""
	for chunk in client.models.generate_content_stream(
		model=model,
		contents=contents,
		config=generate_content_config,
	):
		# print(".",end="", flush=True)
		# print("", flush=True)
		print(chunk.text, end="")
		if chunk.text != None:
			response_text = response_text + chunk.text

	try:
		print("Response from LLM: ", response_text, flush=True)

		response_text = json.loads(response_text)
		print("response_text: ", response_text, flush=True)
		return {'success': True, 'response': response_text}
	except json.JSONDecodeError as e:
		print("Error decoding JSON: ", e)
		return {'success': False, 'response': None, 'log': f"Error decoding JSON: {e} \nResponse text: {response_text}\n-------"}


def ask_llm_compare_wikidata_entity(prompt):

	
	model = GOOGLE_GEMINI_MODEL
	contents = [
		types.Content(
			role="user",
			parts=[
				types.Part.from_text(text=prompt),
			],
		),
	]
	generate_content_config = types.GenerateContentConfig(
		temperature=0,
        # thinking_config = types.ThinkingConfig(
        #     thinking_budget=-1,
        # ),		
		response_mime_type="application/json",
        response_schema=genai.types.Schema(
            type = genai.types.Type.OBJECT,
            required = ["match", "confidence", "reason"],
            properties = {
                "match": genai.types.Schema(
                    type = genai.types.Type.BOOLEAN,
                ),
                "confidence": genai.types.Schema(
                    type = genai.types.Type.INTEGER,
                ),
                "reason": genai.types.Schema(
                    type = genai.types.Type.STRING,
                ),
            },
        ),
        system_instruction=[
            types.Part.from_text(text="""You are a helpful assistant comparing entities between two sources. You will be given an entity and its context it occured in the source and then a possible match from a database.  Compare the context of the entity in the text to the data points from the database. You are trying to identifiy if the two entities are the same thing, the one in the text and the record from the database. Reply in JSON Object with three keys, \"match\" is true or false depending on if it is a match or not and \"confidence\" a percentage 0 to 100 that this is the correct match if it is believed to be a match and \"reason\" a short one sentence explanation for your reasoning. """),
        ],


	)

	response_text = ""
	for chunk in client.models.generate_content_stream(
		model=model,
		contents=contents,
		config=generate_content_config,
	):
		# print(".",end="", flush=True)
		# print("", flush=True)
		print(chunk.text, end="")
		if chunk.text != None:
			response_text = response_text + chunk.text

	try:
		print("Response from LLM: ", response_text, flush=True)

		response_text = json.loads(response_text)
		print("response_text: ", response_text, flush=True)
		return {'success': True, 'response': response_text}
	except json.JSONDecodeError as e:
		print("Error decoding JSON: ", e)
		return {'success': False, 'response': None, 'log': f"Error decoding JSON: {e} \nResponse text: {response_text}\n-------"}



def ask_llm_normalize_labels(prompt):

	
	model = GOOGLE_GEMINI_MODEL
	contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
	generate_content_config = types.GenerateContentConfig(
        temperature=0,
        thinking_config = types.ThinkingConfig(
            thinking_budget=-1,
        ),
        response_mime_type="application/json",
        response_schema=genai.types.Schema(
            type = genai.types.Type.ARRAY,
            items = genai.types.Schema(
                type = genai.types.Type.OBJECT,
                required = ["internal_id", "labels", "normalizedLabels"],
                properties = {
                    "internal_id": genai.types.Schema(
                        type = genai.types.Type.STRING,
                    ),
                    "labels": genai.types.Schema(
                        type = genai.types.Type.ARRAY,
                        items = genai.types.Schema(
                            type = genai.types.Type.STRING,
                        ),
                    ),
                    "normalizedLabels": genai.types.Schema(
                        type = genai.types.Type.ARRAY,
                        items = genai.types.Schema(
                            type = genai.types.Type.STRING,
                        ),
                    ),
                },
            ),
        ),
    )

	response_text = ""
	for chunk in client.models.generate_content_stream(
		model=model,
		contents=contents,
		config=generate_content_config,
	):
		# print(".",end="", flush=True)
		# print("", flush=True)
		print(chunk.text, end="")
		if chunk.text != None:
			response_text = response_text + chunk.text

	try:
		print("Response from LLM: ", response_text, flush=True)

		response_text = json.loads(response_text)
		print("response_text: ", response_text, flush=True)
		return {'success': True, 'response': response_text}
	except json.JSONDecodeError as e:
		print("Error decoding JSON: ", e)
		return {'success': False, 'response': None, 'log': f"Error decoding JSON: {e} \nResponse text: {response_text}\n-------"}


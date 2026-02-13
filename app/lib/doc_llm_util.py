import re
import json
import os
from google import genai
from google.genai import types

GOOGLE_GEMINI_MODEL = "gemini-2.5-flash"

client = genai.Client(
	api_key=os.environ.get("GOOGLE_GENAI"),
)

def _get_client(api_key=None):
	"""Return a genai Client using the given api_key, or the module-level default."""
	if api_key:
		return genai.Client(api_key=api_key)
	return client


def judge_diff(diff, api_key=None):	 

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
	
	c = _get_client(api_key)
	for chunk in c.models.generate_content_stream(
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



def ask_llm_structured(prompt, api_key=None):



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
	c = _get_client(api_key)
	response_text = ""
	for chunk in c.models.generate_content_stream(
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


def ask_llm_reconcile_project_wide(prompt, api_key=None):

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
	c = _get_client(api_key)
	print("here")
	response_text = ""
	for chunk in c.models.generate_content_stream(
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




def ask_llm_reconcile_build_search_order(prompt, api_key=None):

	
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
	c = _get_client(api_key)
	print("here")
	response_text = ""
	for chunk in c.models.generate_content_stream(
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


def ask_llm_compare_wikidata_entity(prompt, api_key=None):

	
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

	c = _get_client(api_key)
	response_text = ""
	for chunk in c.models.generate_content_stream(
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



def ask_llm_normalize_labels(prompt, api_key=None):

	
	model = GOOGLE_GEMINI_MODEL
	contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
	print("Starting normalization process...", flush=True)
	print("Prompt: ", prompt, flush=True)
	generate_content_config = types.GenerateContentConfig(
        temperature=0,
        # thinking_config = types.ThinkingConfig(
        #     thinking_budget=-1,
        # ),
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

	c = _get_client(api_key)
	response_text = ""
	for chunk in c.models.generate_content_stream(
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



def extract_relationships(text, api_key=None):
	"""
	Extract relationships from text using Gemini with thinking mode.

	Args:
		text: The text to extract relationships from

	Returns:
		dict: Response with success status and extracted relationships
	"""
	model = "gemini-flash-latest"
	contents = [
		types.Content(
			role="user",
			parts=[
				types.Part.from_text(text=text),
			],
		),
	]
	generate_content_config = types.GenerateContentConfig(
		temperature=0,
		thinking_config=types.ThinkingConfig(
			thinking_budget=-1,
		),
		response_mime_type="application/json",
	)

	c = _get_client(api_key)
	response_text = ""
	for chunk in c.models.generate_content_stream(
		model=model,
		contents=contents,
		config=generate_content_config,
	):
		print(chunk.text, end="", flush=True)
		if chunk.text is not None:
			response_text += chunk.text

	try:
		print("\nResponse from LLM: ", response_text, flush=True)
		response_json = json.loads(response_text)
		return {'success': True, 'response': response_json}
	except json.JSONDecodeError as e:
		print("Error decoding JSON: ", e, flush=True)
		return {'success': False, 'response': None, 'error': f"Error decoding JSON: {e}\nResponse text: {response_text}"}


def summarize_block_text(block_text, api_key=None):
	"""
	Summarize a block of text into bullet points using Gemini.

	Args:
		block_text: The text to summarize
		api_key: Optional API key override

	Returns:
		str: The summary as a bulleted list
	"""
	model = GOOGLE_GEMINI_MODEL
	contents = [
		types.Content(
			role="user",
			parts=[
				types.Part.from_text(text=block_text),
			],
		),
	]
	generate_content_config = types.GenerateContentConfig(
		system_instruction=[
			types.Part.from_text(text="""You are a research assistant specializing in transformative summarization. Your task is to read the following source text and produce a bullet-point summary that captures the key ideas while being fully original in its expression.
Rules you must follow:

Never borrow phrasing from the source. Every bullet point must be written entirely in your own words. Do not quote, echo, or closely paraphrase the original language — restate concepts using different vocabulary, sentence structure, and framing.
Be transformative, not duplicative. Your goal is to distill and reinterpret the information for a reader who needs a quick, high-level understanding. Add analytical context where helpful (e.g., noting why a point matters or how ideas connect to each other).
Condense significantly. Do not attempt to reproduce the full detail or structure of the original.
Use a neutral, informational tone appropriate for personal research notes.
Omit any decorative language, stylistic flourishes, or distinctive creative expressions from the source — focus purely on the underlying facts and ideas.
Do not reproduce any lists, tables, or structured data from the source verbatim.

Format: Return ONLY a bulleted list of no more than 8–12 points (fewer if the text is short). Each bullet should be 1–2 sentences. Do not include any introductory text, headers, or concluding remarks — start directly with the first bullet point.

Source text to summarize:"""),
		],
	)

	c = _get_client(api_key)
	response_text = ""
	for chunk in c.models.generate_content_stream(
		model=model,
		contents=contents,
		config=generate_content_config,
	):
		if chunk.text is not None:
			response_text += chunk.text

	return response_text

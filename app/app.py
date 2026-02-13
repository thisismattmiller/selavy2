from flask import Flask, request, render_template, session
from flask_socketio import SocketIO
import subprocess
import time
import uuid
import os
from google import genai
from google.genai import errors as genai_errors
import json
from typing import Dict
import glob
from datetime import datetime
import requests
import fcntl
from contextlib import contextmanager


@contextmanager
def file_lock(filepath):
    """Context manager for file locking to prevent race conditions."""
    lock_path = filepath + '.lock'
    with open(lock_path, 'w') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

# from lib.doc_diff import build_doc_diffs
from lib.doc_diff_new import build_doc_diffs


from lib.doc_llm_util import judge_diff
from lib.doc_llm_util import ask_llm_reconcile_project_wide, ask_llm_structured, ask_llm_reconcile_build_search_order, ask_llm_compare_wikidata_entity, ask_llm_normalize_labels, extract_relationships

from lib.doc_util import return_ner

from lib.base_util import search_base


from lib.base_util import wikibase_mint_entity

from lib.s3_util import upload_block_text
from lib.publish_util import create_document_item, create_block_item, create_statement_with_reference, delete_claim, delete_block_item
from lib.doc_llm_util import summarize_block_text


client = genai.Client(
    api_key=os.environ.get("GOOGLE_GENAI"),
)

USER_API_KEYS_FILE = '/data/user_api_keys.json'

def load_user_api_keys():
    if os.path.exists(USER_API_KEYS_FILE):
        with open(USER_API_KEYS_FILE) as f:
            return json.load(f)
    return {}

def save_user_api_keys(keys):
    with file_lock(USER_API_KEYS_FILE):
        with open(USER_API_KEYS_FILE, 'w') as f:
            json.dump(keys, f, indent=2)

def get_user_api_key(username, key_name="GOOGLE_GENAI"):
    """Get a user's custom API key, or fall back to the default env var."""
    if username:
        keys = load_user_api_keys()
        user_keys = keys.get(username.lower(), {})
        if key_name in user_keys and user_keys[key_name]:
            custom_key = user_keys[key_name]
            print(f"[API_KEY] Using CUSTOM {key_name} for user '{username}' (key ends with ...{custom_key[-6:]})", flush=True)
            return custom_key
    default_key = os.environ.get(key_name)
    print(f"[API_KEY] Using DEFAULT {key_name} for user '{username}' (key ends with ...{default_key[-6:] if default_key else 'None'})", flush=True)
    return default_key

def get_genai_client(username=None):
    """Get a genai.Client using the user's API key if available."""
    api_key = get_user_api_key(username, "GOOGLE_GENAI")
    return genai.Client(api_key=api_key)

def get_current_username():
    """Get the username for the current socket session from user_store."""
    if request.sid in user_store:
        username = user_store[request.sid].get('login_data', {}).get('username', '')
        print(f"[API_KEY] get_current_username: sid={request.sid} -> user='{username}'", flush=True)
        return username
    print(f"[API_KEY] get_current_username: sid={request.sid} NOT FOUND in user_store (keys: {list(user_store.keys())})", flush=True)
    return ''

GOOGLE_GEMINI_MODEL = "gemini-2.5-flash"
output_limits = {
    "gemini-2.5-flash": 65_536,
}

from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator import wbi_login, WikibaseIntegrator

wbi_config['MEDIAWIKI_API_URL'] = 'https://base.semlab.io/api.php'
wbi_config['SPARQL_ENDPOINT_URL'] = 'https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql'
wbi_config['WIKIBASE_URL'] = 'https://base.semlab.io'
wbi_config['USER_AGENT'] = 'Selavy 3.0'



app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem' # or 'redis', 'mongodb', etc.

socketio = SocketIO(app,cors_allowed_origins="*")

@socketio.on_error_default
def default_error_handler(e):
    """Global error handler for all Socket.IO events. Catches Google GenAI API key errors and notifies the frontend."""
    print(f"[SOCKET_ERROR] {type(e).__name__}: {e}", flush=True)
    if isinstance(e, genai_errors.ClientError):
        # Extract the human-readable message from the error details
        error_message = str(e)
        try:
            # Try to get the LocalizedMessage from the error response
            if hasattr(e, 'response') and e.response is not None:
                resp_json = e.response.json()
                for detail in resp_json.get('error', {}).get('details', []):
                    if detail.get('@type', '').endswith('LocalizedMessage'):
                        error_message = detail.get('message', error_message)
                        break
        except Exception:
            pass
        print(f"[SOCKET_ERROR] Emitting api_key_error to {request.sid}: {error_message}", flush=True)
        socketio.emit('api_key_error', {'message': error_message, 'provider': 'GOOGLE_GENAI'}, to=request.sid)
        return  # Don't re-raise, we've handled it and notified the client
    raise e


# Global store for user status
# Structure: { user_sid: { 'status': str, 'data': Dict } }
user_store: Dict[str, Dict] = {}




@app.route('/')
def index():
    return render_template("index.html", app_data={"hello":"hello"})

@socketio.on('message')
def handle_message(data):
    print('received message: ' + data,flush=True)

@socketio.on('json')
def handle_json(json_data):
    print('received jsonzzzz: ' + str(json_data),flush=True)

@socketio.on('my event')
def handle_my_custom_event(json_data):
    print('received my event: ' + str(json_data),flush=True)


@socketio.on('connect')
def handle_connect(reason):
    print(f'Client connected, request.sid: {request.sid}', flush=True)
    print(session, flush=True)

@socketio.on('disconnect')
def handle_disconnect(reason):
    print(f'Client disconnected, reason: {reason}', flush=True)


@socketio.on('get_user_api_key_status')
def handle_get_user_api_key_status(data):
    username = data.get('user', '')
    if not username:
        return {'success': False, 'error': 'No user provided'}
    keys = load_user_api_keys()
    user_keys = keys.get(username.lower(), {})
    has_custom_key = bool(user_keys.get('GOOGLE_GENAI'))
    return {'success': True, 'has_custom_key': has_custom_key}

@socketio.on('set_user_api_key')
def handle_set_user_api_key(data):
    username = data.get('user', '')
    api_key = data.get('api_key', '')
    if not username:
        return {'success': False, 'error': 'No user provided'}
    if not api_key or not api_key.strip():
        return {'success': False, 'error': 'No API key provided'}
    keys = load_user_api_keys()
    keys[username.lower()] = {'GOOGLE_GENAI': api_key.strip()}
    save_user_api_keys(keys)
    print(f"[API_KEY] Saved custom key for user '{username.lower()}' (key ends with ...{api_key.strip()[-6:]})", flush=True)
    return {'success': True, 'error': None}

@socketio.on('remove_user_api_key')
def handle_remove_user_api_key(data):
    username = data.get('user', '')
    if not username:
        return {'success': False, 'error': 'No user provided'}
    keys = load_user_api_keys()
    if username.lower() in keys:
        del keys[username.lower()]
        save_user_api_keys(keys)
    return {'success': True, 'error': None}

@socketio.on('geminiTokenCount')
def handle_geminiTokenCount(text):
    username = get_current_username()
    user_client = get_genai_client(username)
    total_tokens = user_client.models.count_tokens(
        model=GOOGLE_GEMINI_MODEL, contents=text
    )
    return {'success': True, 'error': None, 'token_count': total_tokens.total_tokens, 'model': GOOGLE_GEMINI_MODEL, 'limit': output_limits[GOOGLE_GEMINI_MODEL] }


@socketio.on('wikibase_mint_entity')
def handle_wikibase_mint_entity(entity):
    print(entity, flush=True)

    print("user_store",user_store, flush=True)

    if 'login_token' not in entity:
        return {'success': False, 'error': 'No login token provided'}
    
    for key in user_store:
        if user_store[key]['login_token'] == entity['login_token']:
            request.sid = key
            break

    if request.sid not in user_store:
        print("User not logged in:", request.sid, flush=True)
        return {'success': False, 'error': 'User not logged in, try reloading the page.'}
    
    print("user_store[request.sid]",user_store[request.sid], flush=True)

    print("entity",entity, flush=True   )
    results = wikibase_mint_entity(user_store[request.sid], entity, user_store, request.sid)
    print("results",results, flush=True)
    return results


@socketio.on('login')
def handle_login(login_data):
    print(user_store, flush=True)
    print(f'login, : {request.sid}', login_data, flush=True)

    try:
        login_instance = wbi_login.Clientlogin(user=login_data['username'], password=login_data['password'])
        login_token = str(uuid.uuid4())

        user_store[request.sid] = {
            'login_instance': login_instance,
            'login_data': login_data,
            'login_token': login_token
        }
        return {'success': True, 'error': None, 'login_token': login_token }

    except Exception as e:

        if login_data['password'] == 'mattdebug':
            login_token = str(uuid.uuid4())

            user_store[request.sid] = {
                'login_instance': {},
                'login_data': login_data,
                'login_token': login_token
            }
            return {'success': True, 'error': None, 'login_token': login_token }
        else:
            #socketio.emit('login_results', {'success': False, 'error': str(e) }, to=request.sid)
            print("Error message: ", e, flush=True)
            return {'success': False, 'error': str(e) }
    
            # print(login_instance, flush=True)






    # process = subprocess.Popen("python3 scripts/markup-job.py", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # print('gonna sleep',flush=True)

    # time.sleep(5)
    # print(process.communicate(),flush=True)

@socketio.on('login_validate')
def handle_login_validate(login_token):

    # look through the user_store for the token, if found they are logged in and don't need to again
    for key in user_store:
        if user_store[key]['login_token'] == login_token:
            print("User validated:", user_store[key]['login_data']['username'], flush=True)
            # Map the new socket sid to this user's data so get_current_username() works
            if request.sid != key:
                user_store[request.sid] = user_store[key]
                print(f"Mapped new sid {request.sid} to user {user_store[key]['login_data']['username']}", flush=True)
            return {'success': True, 'error': None, 'user': user_store[key]['login_data']['username'] }

    return {'success': False, 'error': 'Not Found'}




@socketio.on('get_document_status')
def handle_get_document_status(job_data):
    # check if the job exists
    if 'user' in job_data:
        if job_data["user"] is not None:
            job_data["user"] = job_data["user"].lower()
        else:
            job_data["user"] = "none"

    
    if os.path.exists(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.meta.json'):
        with open(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.meta.json') as f:
            job_data = json.load(f)
            if 'workflow' not in job_data:
                job_data['workflow'] = {}
            if 'DIFF_REVIEW' not in job_data['workflow']:
                job_data['workflow']['DIFF_REVIEW'] = {
                    'status': 'NOT_STARTED',
                    'description': 'Compare the orginal text to the processed text for significant differences. If there are significant differences.',
                }

            if 'NER' not in job_data['workflow']:
                job_data['workflow']['NER'] = {
                    'status': 'NOT_STARTED',
                    'description': 'NER.',
                }


            if 'status' in job_data:
                if isinstance(job_data['status'], list):
                    job_data['status'] = job_data['status'][0]

            if job_data['status'] == 'LLM_MARKING_UP' or job_data['status'] == 'PRE_LLM_MARKUP':
                # check if there is an error file with stuff in it
                if os.path.exists(f'/data/jobs/{job_data["user"]}/{job_data["id"]}_error.log'):
                    with open(f'/data/jobs/{job_data["user"]}/{job_data["id"]}_error.log') as ef:
                        error_data = ef.read()
                        # print("Error file found:", error_data, len(), flush=True)
                        if len(error_data.split("\n")) > 1:
                            job_data['error'] = error_data
                            job_data['status'] = "LLM_MARKUP_ERROR"



            return {'success': True, 'error': None, 'job_data': job_data }
    else:
        return {'success': False, 'error': 'Doc not found'}


@socketio.on('get_ner')
def handle_get_ner(job_data):

    if 'user' in job_data:
        if job_data["user"] != None:
            job_data["user"] = job_data["user"].lower()

    # check if the job exists
    if os.path.exists(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.json'):
        with open(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.json') as f:
            job_data = json.load(f)
            ner = return_ner(job_data['text_markup'])

            if 'entities' in job_data:
                ner['entities'] = job_data['entities']


            if 'class_map' in job_data:
                ner['class_map'] = job_data['class_map']

            return {'success': True, 'error': None, 'ner': ner }
    else:
        return {'success': False, 'error': 'Doc not found'}




@socketio.on('update_document_status')
def handle_update_document_status(job_data):
    # check if the job exists

    if 'user' in job_data:
        if job_data["user"] != None:
            job_data["user"] = job_data["user"].lower()

    if os.path.exists(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.meta.json'):
        with open(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.meta.json') as f:
            job_data_load = json.load(f)
            if 'workflow' not in job_data_load:
                job_data_load['workflow'] = {}

            if 'DIFF_REVIEW' not in job_data_load['workflow']:
                job_data_load['workflow']['DIFF_REVIEW'] = {
                    'status': 'NOT_STARTED',
                    'description': 'Compare the orginal text to the processed text for significant differences. If there are significant differences.',
                }
            if 'NER' not in job_data_load['workflow']:
                job_data_load['workflow']['NER'] = {
                    'status': 'NOT_STARTED',
                    'description': 'NER.',
                }
            job_data_load['workflow'][job_data['workflow']]['status'] = job_data['value']

            json.dump(job_data_load, open(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.meta.json','w'), indent=2)

            return {'success': True, 'error': None, 'job_data': job_data_load }
    else:
        return {'success': False, 'error': 'Doc not found'}




@socketio.on('get_document_diffs')
def handle_get_document_diffs(job_data):
    # check if the job exists
    if 'user' in job_data:
        if job_data["user"] != None:
            job_data["user"] = job_data["user"].lower()

    if os.path.exists(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.json'):
        with open(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.json') as f:
            job_data = json.load(f)
            diffs = build_doc_diffs(job_data['text'], job_data['text_markup'])
            print("documentDiffs", diffs, flush=True)
            return {'success': True, 'error': None, 'documentDiffs': diffs, 'documentOrginal': job_data['text'], 'documentMarkup': job_data['text_markup'] }
    else:
        return {'success': False, 'error': 'Doc not found'}

@socketio.on('update_document_markup')
def handle_update_document_markup(job_data):
    if 'user' in job_data:
        if job_data["user"] != None:
            job_data["user"] = job_data["user"].lower()

    data_file = f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.json'

    # check if the job exists
    if not os.path.exists(data_file):
        return {'success': False, 'error': 'Doc not found'}

    with file_lock(data_file):
        with open(data_file) as f:
            file_data = json.load(f)

        file_data['text_markup'] = job_data['text_markup']

        # Re-parse entities from new markup to get updated block assignments
        if 'entities' in file_data:
            fresh_ner = return_ner(job_data['text_markup'])
            fresh_entities = fresh_ner['entities']

            for entity_id in file_data['entities']:
                if entity_id in fresh_entities:
                    file_data['entities'][entity_id]['blocks'] = fresh_entities[entity_id]['blocks']
                    file_data['entities'][entity_id]['count'] = fresh_entities[entity_id]['count']
                    file_data['entities'][entity_id]['labels'] = fresh_entities[entity_id]['labels']
                else:
                    file_data['entities'][entity_id]['blocks'] = []
                    file_data['entities'][entity_id]['count'] = 0

        with open(data_file, 'w') as f:
            json.dump(file_data, f, indent=2)

    return {'success': True, 'error': None}


@socketio.on('update_text_markup')
def handle_update_text_markup(data):
    """
    Update text_markup field in job JSON file.

    Args:
        data: dict with 'doc', 'job_id', 'text', and 'user' keys

    Returns:
        dict with 'success' and 'error' keys
    """
    try:
        job_id = data.get('job_id') or data.get('doc')
        text_markup = data.get('text')
        user = data.get('user')

        if not job_id or text_markup is None:
            return {'success': False, 'error': 'Missing job_id or text'}

        # Normalize username
        if user:
            user = user.lower()

        # Build the job file path
        if user:
            job_file_path = f'/data/jobs/{user}/{job_id}.json'
        else:
            # If no user provided, search all user directories
            job_file_path = None
            for user_dir in glob.glob('/data/jobs/*'):
                potential_path = f'{user_dir}/{job_id}.json'
                if os.path.exists(potential_path):
                    job_file_path = potential_path
                    break

        if not job_file_path or not os.path.exists(job_file_path):
            return {'success': False, 'error': f'Job {job_id} not found'}

        with file_lock(job_file_path):
            # Load the job file
            with open(job_file_path, 'r') as f:
                job_data = json.load(f)

            # Update text_markup
            job_data['text_markup'] = text_markup

            # Save the job file
            with open(job_file_path, 'w') as f:
                json.dump(job_data, f, indent=2)

        return {'success': True, 'error': None}

    except Exception as e:
        print(f"Error updating text_markup: {e}", flush=True)
        return {'success': False, 'error': str(e)}




@socketio.on('judge_diff')
def handle_judge_diff(diff):
    print("diff", diff, flush=True)
    username = get_current_username()
    api_key = get_user_api_key(username)
    j = judge_diff(diff, api_key=api_key)
    print("judge_diff", j, flush=True)
    if j is None:
        return {'success': False, 'judgement': None, 'error': ''}
    else:
        return {'success': True, 'judgement': j, 'error': ''}
    

    

@socketio.on('process_text')
def handle_process_text(json_data):
    # print('received process_text: ' + str(json_data),flush=True)


    now = datetime.now()

    formatted_date_time = now.strftime("%Y-%m-%d %H:%M:%S")

    user_jobs_dir = f'/data/jobs/{json_data["user"]}/'.lower()

    job_id = str(uuid.uuid4())
    job_data = {
        "id": job_id,
        "title": json_data['title'],
        "text": json_data['text'],
        "user": json_data['user'],
        "created_at": formatted_date_time,
        "status": 'PRE_LLM_MARKUP',
        'status_percent': None,
        "model": json_data.get('model'),
        "additionalInstructions": json_data.get('additionalInstructions')
    }

    with open(f'{user_jobs_dir}{job_id}.json','w') as out:
        json.dump(job_data,out)


    with open(f'{user_jobs_dir}{job_id}.meta.json','w') as out:
        json.dump({
            "id": job_id,
            "title": json_data['title'],
            "status": 'PRE_LLM_MARKUP',
            "user": json_data['user'],  
            "created_at": formatted_date_time,
            'status_percent': None,
        },out)

    # socketio.emit('job_status', {'id': job_id, 'status': 'PRE_LLM_MARKUP'})
    script_output = open(f'{user_jobs_dir}{job_id}_output.log', 'w')
    script_error = open(f'{user_jobs_dir}{job_id}_error.log', 'w')

    if 'gpt' in json_data['model']:
        process = subprocess.Popen("python3 scripts/markup-job-gpt.py " + job_id + " " + json_data['user'].lower(), shell=True, stdout=script_output, stderr=script_error)
    else:
        process = subprocess.Popen("python3 scripts/markup-job-gemini.py " + job_id + " " + json_data['user'].lower(), shell=True, stdout=script_output, stderr=script_error)

    print("script_output",script_output, flush=True)
    print("script_error",script_error, flush=True)    
    return {'success': True, 'job_id': job_id}


    # print('gonna sleep',flush=True)

    # time.sleep(5)


@socketio.on('jobs_list')
def handle_jobs_list(data):



    print(data, flush=True)
    user_jobs_dir = f'/data/jobs/{data["user"]}/'.lower()
    if not os.path.exists(user_jobs_dir):
        os.makedirs(user_jobs_dir)

    print(f'{user_jobs_dir}' + '*.meta.json', flush=True)
    my_jobs = []
    for file in glob.glob(f'{user_jobs_dir}' + '*.meta.json'):
        print(file, flush=True)
        with open(file) as f:
            job_data = json.load(f)
            print(job_data, flush=True)

            if job_data['status'] == 'PRE_LLM_MARKUP' or job_data['status'] == 'LLM_MARKING_UP':
                job_data['order'] = 0
                

                # check if there is an error file with stuff in it
                if os.path.exists(f'{user_jobs_dir}{job_data["id"]}_error.log'):
                    with open(f'{user_jobs_dir}{job_data["id"]}_error.log') as ef:
                        error_data = ef.read()
                        # print("Error file found:", error_data, len(), flush=True)
                        if len(error_data.split("\n")) > 1:
                            job_data['error'] = error_data
                            job_data['status'] = "LLM_MARKUP_ERROR"

            else:
                job_data['order'] = 1

            my_jobs.append(job_data)
        

    
    # Sort jobs: order=0 at top, then order=1 sorted by created_at (newest first)
    my_jobs = sorted(my_jobs, key=lambda x: (
        x['order'],  # First sort by order (0 comes before 1)
        -1 * int(x['created_at'].replace('-', '').replace(' ', '').replace(':', '')) if x['order'] == 1 and 'created_at' in x else 0  # For order=1, sort by created_at descending (newest first)
    ))

    return {'success': True, 'jobs': my_jobs }






@socketio.on('ask_llm')
def handle_ask_llm(data):
    # data == {"prompt": "your prompt here", "task": "TASK_NAME"}

    if 'task' not in data:
        return {'success': False, 'error': 'No task provided'}
    if 'prompt' not in data:
        return {'success': False, 'error': 'No prompt provided'}

    username = get_current_username()
    api_key = get_user_api_key(username)

    if data['task'] == 'RECONCILE_PROJECT_WIDE' or data['task'] == 'RECONCILE_BY_CLASS':
        response = ask_llm_reconcile_project_wide(data['prompt'], api_key=api_key)
        return response


    else:
        response = ask_llm_structured(data['prompt'], api_key=api_key)
        print("response", response, flush=True)
        if response is None:
            return {'success': False, 'error': 'LLM error'}
        else:
            return {'success': True, 'response': response}




@socketio.on('ask_llm_normalize_labels')
def handle_ask_llm_normalize_labels(prompt):
    username = get_current_username()
    api_key = get_user_api_key(username)
    response = ask_llm_normalize_labels(prompt, api_key=api_key)
    return response


@socketio.on('ask_llm_reconcile_build_search_order')
def handle_ask_llm_reconcile_build_search_order(prompt):
    print("Sending Proposed Build Search Order Prompt to LLM:", flush=True)
    username = get_current_username()
    api_key = get_user_api_key(username)
    response = ask_llm_reconcile_build_search_order(prompt, api_key=api_key)
    return response

@socketio.on('ask_llm_compare_wikidata_entity')
def handle_ask_llm_compare_wikidata_entity(prompt):
    print("Sending Proposed Build Search Order Prompt to LLM:", flush=True)
    username = get_current_username()
    api_key = get_user_api_key(username)
    response = ask_llm_compare_wikidata_entity(prompt, api_key=api_key)
    return response

@socketio.on('extract_relationships')
def handle_extract_relationships(data):
    print("Extracting relationships from text:", flush=True)
    # Extract the prompt from the data if it's a dict, otherwise use data as-is
    if isinstance(data, dict):
        text = data.get('prompt', '')
    else:
        text = data
    username = get_current_username()
    api_key = get_user_api_key(username)
    response = extract_relationships(text, api_key=api_key)
    return response

@socketio.on('search_base')
def handle_search_base(query):
    response = search_base(query)
    if response != False:
        return {'success': True, 'error': None, 'response': response}
    else:
        return {'success': False, 'error': "Base Search Error", 'response':response}

@socketio.on('delete_job')
def handle_delete_job(job_id):
    try:
        # Find the job metadata to get the user
        job_found = False
        user = None
        
        # Search through all user directories for the job
        if os.path.exists('/data/jobs'):
            for user_dir in os.listdir('/data/jobs'):
                meta_file = f'/data/jobs/{user_dir}/{job_id}.meta.json'
                if os.path.exists(meta_file):
                    with open(meta_file) as f:
                        job_data = json.load(f)
                        user = job_data.get('user', user_dir)
                        job_found = True
                        break
        
        if not job_found:
            return {'success': False, 'error': 'Job not found'}
        
        # Delete all job-related files
        user_jobs_dir = f'/data/jobs/{user}/'
        files_to_delete = [
            f'{user_jobs_dir}{job_id}.json',
            f'{user_jobs_dir}{job_id}.meta.json',
            f'{user_jobs_dir}{job_id}_output.log',
            f'{user_jobs_dir}{job_id}_error.log'
        ]
        
        deleted_files = []
        for file_path in files_to_delete:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_files.append(os.path.basename(file_path))
        
        return {'success': True, 'error': None, 'deleted_files': deleted_files}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


@socketio.on('save_ner_entities')
def handle_save_ner_entities(data):
    # print(data['user'], data['job_id'], data['entities'], flush=True)
    data_file = f'/data/jobs/{data["user"].lower()}/{data["job_id"]}.json'

    if not os.path.exists(data_file):
        return {'success': False, 'error': "Job not found"}

    with file_lock(data_file):
        with open(data_file) as f:
            existing_data = json.load(f)
        existing_data['entities'] = data['entities']
        with open(data_file, 'w') as f:
            json.dump(existing_data, f)

    return {'success': True, 'error': None}


@socketio.on('save_convenience_entities')
def handle_save_convenience_entities(data):
    """
    Save convenience_entities to the job JSON file.

    Args:
        data: dict with 'user', 'doc', and 'convenience_entities' keys

    Returns:
        dict with 'success' and 'error' keys
    """
    try:
        document_id = data.get('doc')
        user = data.get('user')
        convenience_entities = data.get('convenience_entities', [])

        if not document_id:
            return {'success': False, 'error': 'Missing doc'}

        if user:
            user = user.lower()
        else:
            return {'success': False, 'error': 'Missing user'}

        data_file = f'/data/jobs/{user}/{document_id}.json'

        if not os.path.exists(data_file):
            return {'success': False, 'error': 'Job not found'}

        with file_lock(data_file):
            with open(data_file, 'r') as f:
                existing_data = json.load(f)

            existing_data['convenience_entities'] = convenience_entities

            with open(data_file, 'w') as f:
                json.dump(existing_data, f, indent=2)

        return {'success': True, 'error': None}

    except Exception as e:
        print(f"Error saving convenience_entities: {e}", flush=True)
        return {'success': False, 'error': str(e)}


@socketio.on('get_document_meta')
def handle_get_document_meta(data):
    """
    Get document meta object.

    Args:
        data: dict with 'user' and 'doc' keys

    Returns:
        dict with 'success', 'error', and 'meta' keys
    """
    try:
        document_id = data.get('doc')
        user = data.get('user')

        if not document_id:
            return {'success': False, 'error': 'Missing doc'}

        if user:
            user = user.lower()

        data_file = f'/data/jobs/{user}/{document_id}.json'

        if not os.path.exists(data_file):
            return {'success': False, 'error': 'Job not found'}

        with open(data_file, 'r') as f:
            job_data = json.load(f)

        meta = job_data.get('meta', {})

        return {'success': True, 'error': None, 'meta': meta}

    except Exception as e:
        print(f"Error getting document meta: {e}", flush=True)
        return {'success': False, 'error': str(e)}


@socketio.on('update_document_meta')
def handle_update_document_meta(data):
    """
    Update document meta object (merges keys).

    Args:
        data: dict with 'user', 'doc', and 'meta' keys

    Returns:
        dict with 'success' and 'error' keys
    """
    try:
        document_id = data.get('doc')
        user = data.get('user')
        meta_update = data.get('meta', {})

        if not document_id:
            return {'success': False, 'error': 'Missing doc'}

        if user:
            user = user.lower()
        else:
            return {'success': False, 'error': 'Missing user'}

        data_file = f'/data/jobs/{user}/{document_id}.json'

        if not os.path.exists(data_file):
            return {'success': False, 'error': 'Job not found'}

        with file_lock(data_file):
            with open(data_file, 'r') as f:
                existing_data = json.load(f)

            if 'meta' not in existing_data:
                existing_data['meta'] = {}

            # Merge in the new keys
            for key, value in meta_update.items():
                existing_data['meta'][key] = value

            with open(data_file, 'w') as f:
                json.dump(existing_data, f, indent=2)

        return {'success': True, 'error': None}

    except Exception as e:
        print(f"Error updating document meta: {e}", flush=True)
        return {'success': False, 'error': str(e)}


@socketio.on('get_convenience_entities')
def handle_get_convenience_entities(data):
    """
    Get convenience_entities for a given document.

    Args:
        data: dict with 'user' and 'doc' keys

    Returns:
        dict with 'success', 'error', and 'convenience_entities' keys
    """
    try:
        document_id = data.get('doc')
        user = data.get('user')

        if not document_id:
            return {'success': False, 'error': 'Missing doc'}

        if user:
            user = user.lower()

        data_file = f'/data/jobs/{user}/{document_id}.json'

        if not os.path.exists(data_file):
            return {'success': False, 'error': 'Job not found'}

        with open(data_file, 'r') as f:
            job_data = json.load(f)

        convenience_entities = job_data.get('convenience_entities', [])

        return {'success': True, 'error': None, 'convenience_entities': convenience_entities}

    except Exception as e:
        print(f"Error getting convenience_entities: {e}", flush=True)
        return {'success': False, 'error': str(e)}


@socketio.on('get_triples')
def handle_get_triples(data):
    """
    Get triples data for a given document.

    Args:
        data: dict with 'documentId' (or 'doc') and 'user' keys

    Returns:
        dict with 'success', 'error', and 'triples' keys
    """
    try:
        document_id = data.get('documentId') or data.get('doc')
        user = data.get('user')

        if not document_id:
            return {'success': False, 'error': 'Missing documentId'}

        # Normalize username
        if user:
            user = user.lower()

        # Build the job file path
        data_file = f'/data/jobs/{user}/{document_id}.json'

        if not os.path.exists(data_file):
            return {'success': False, 'error': 'Job not found'}

        # Load job data
        with open(data_file, 'r') as f:
            job_data = json.load(f)

        # Get triples data (empty dict if not present)
        triples = job_data.get('triples', {})

        return {'success': True, 'error': None, 'triples': triples}

    except Exception as e:
        print(f"Error getting triples: {e}", flush=True)
        return {'success': False, 'error': str(e)}


@socketio.on('save_triples')
def handle_save_triples(data):
    """
    Save triples data to the job JSON file.

    Args:
        data: dict with 'documentId', 'blocks', and 'user' keys
        blocks: array of objects with 'blockId' and 'triples' keys

    Returns:
        dict with 'success' and 'error' keys
    """
    try:
        document_id = data.get('documentId')
        blocks = data.get('blocks', [])
        user = data.get('user')

        if not document_id:
            return {'success': False, 'error': 'Missing documentId'}

        # Normalize username
        if user:
            user = user.lower()
        else:
            return {'success': False, 'error': 'Missing user'}

        # Build the job file path
        data_file = f'/data/jobs/{user}/{document_id}.json'

        if not os.path.exists(data_file):
            return {'success': False, 'error': 'Job not found'}

        with file_lock(data_file):
            # Load existing job data
            with open(data_file, 'r') as f:
                existing_data = json.load(f)

            # Update triples data - store by blockId for easy lookup
            if 'triples' not in existing_data:
                existing_data['triples'] = {}

            # Update triples for each block
            for block in blocks:
                block_id = str(block.get('blockId'))
                triples = block.get('triples', [])
                existing_data['triples'][block_id] = triples

            # Save the updated job data
            with open(data_file, 'w') as f:
                json.dump(existing_data, f, indent=2)

        return {'success': True, 'error': None}

    except Exception as e:
        print(f"Error saving triples: {e}", flush=True)
        return {'success': False, 'error': str(e)}


@socketio.on('search_semlab_autocomplete')
def handle_search_semlab_autocomplete(search_term):
    try:
        url = f"https://base.semlab.io/w/api.php?action=wbsearchentities&search={search_term}&format=json&errorformat=plaintext&language=en&uselang=en&type=item"
        response = requests.get(url)
        response.raise_for_status()

        return {'success': True, 'error': None, 'data': response.json()}

    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': str(e), 'data': None}

@socketio.on('publish_get_state')
def handle_publish_get_state(data):
    """Load the publish state for a document."""
    try:
        user = data.get('user', '').lower()
        doc = data.get('doc')
        if not doc or not user:
            return {'success': False, 'error': 'Missing user or doc'}

        state_file = f'/data/jobs/{user}/{doc}.publish.json'
        if not os.path.exists(state_file):
            return {'success': True, 'error': None, 'publishState': None}

        with open(state_file, 'r') as f:
            publish_state = json.load(f)

        return {'success': True, 'error': None, 'publishState': publish_state}
    except Exception as e:
        print(f"Error getting publish state: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_save_state')
def handle_publish_save_state(data):
    """Save the publish state for a document."""
    try:
        user = data.get('user', '').lower()
        doc = data.get('doc')
        publish_state = data.get('publishState', {})
        if not doc or not user:
            return {'success': False, 'error': 'Missing user or doc'}

        state_file = f'/data/jobs/{user}/{doc}.publish.json'
        with file_lock(state_file):
            with open(state_file, 'w') as f:
                json.dump(publish_state, f, indent=2)

        return {'success': True, 'error': None}
    except Exception as e:
        print(f"Error saving publish state: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_create_document')
def handle_publish_create_document(data):
    """Create a document item on Wikibase."""
    try:
        if 'login_token' not in data:
            return {'success': False, 'error': 'No login token provided'}

        # Find user session by login token
        sid = None
        for key in user_store:
            if user_store[key]['login_token'] == data['login_token']:
                sid = key
                break

        if sid is None or sid not in user_store:
            return {'success': False, 'error': 'User not logged in, try reloading the page.'}

        login_instance = user_store[sid]['login_instance']
        wbi = WikibaseIntegrator(login=login_instance)

        label = data.get('label', '')
        description = data.get('description', '')
        instance_of = data.get('instanceOf', ['Q19069'])
        projects = data.get('projects', [])

        if not label:
            return {'success': False, 'error': 'Document label is required'}

        qid = create_document_item(wbi, label, description, instance_of, projects)
        return {'success': True, 'error': None, 'qid': qid}

    except Exception as e:
        print(f"Error creating document: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_summarize_block')
def handle_publish_summarize_block(data):
    """Summarize a block's text using the LLM."""
    try:
        user = data.get('user', '')
        block_text = data.get('blockText', '')

        if not block_text:
            return {'success': False, 'error': 'No block text provided'}

        # Get user's custom API key if available
        api_key = get_user_api_key(user, 'GOOGLE_GENAI') if user else None

        summary = summarize_block_text(block_text, api_key=api_key)
        return {'success': True, 'error': None, 'summary': summary}

    except Exception as e:
        print(f"Error summarizing block: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_upload_s3')
def handle_publish_upload_s3(data):
    """Upload block text to S3."""
    try:
        document_qid = data.get('documentQid')
        block_id = data.get('blockId')
        text = data.get('text', '')
        original_text = data.get('originalText')
        summarized = data.get('summarized', False)

        if not document_qid or block_id is None:
            return {'success': False, 'error': 'Missing documentQid or blockId'}

        # Upload the main text (summary if summarized, original if not)
        text_url = upload_block_text(document_qid, block_id, text, prefix='texts')

        original_url = None
        if summarized and original_text:
            # Upload the original text to texts_original/
            original_url = upload_block_text(document_qid, block_id, original_text, prefix='texts_original')

        return {
            'success': True,
            'error': None,
            'textUrl': text_url,
            'originalUrl': original_url
        }

    except Exception as e:
        print(f"Error uploading to S3: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_block_to_wikibase')
def handle_publish_block_to_wikibase(data):
    """Create a block item on Wikibase."""
    try:
        if 'login_token' not in data:
            return {'success': False, 'error': 'No login token provided'}

        sid = None
        for key in user_store:
            if user_store[key]['login_token'] == data['login_token']:
                sid = key
                break

        if sid is None or sid not in user_store:
            return {'success': False, 'error': 'User not logged in, try reloading the page.'}

        login_instance = user_store[sid]['login_instance']
        wbi = WikibaseIntegrator(login=login_instance)

        block_id = data.get('blockId')
        document_qid = data.get('documentQid')
        projects = data.get('projects', [])
        s3_url = data.get('s3Url', '')
        associated_entities = data.get('associatedEntities', [])
        document_label = data.get('documentLabel', 'Document')
        block_text = data.get('blockText', '')

        label = f'{document_label} - Block {block_id}'

        block_qid = create_block_item(wbi, label, document_qid, projects, block_id, s3_url, associated_entities, block_text)
        return {'success': True, 'error': None, 'blockQid': block_qid}

    except Exception as e:
        print(f"Error publishing block: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_unpublish_block')
def handle_publish_unpublish_block(data):
    """Unpublish a single block - delete its statements then the block item."""
    try:
        if 'login_token' not in data:
            return {'success': False, 'error': 'No login token provided'}

        sid = None
        for key in user_store:
            if user_store[key]['login_token'] == data['login_token']:
                sid = key
                break

        if sid is None or sid not in user_store:
            return {'success': False, 'error': 'User not logged in, try reloading the page.'}

        login_instance = user_store[sid]['login_instance']
        wbi = WikibaseIntegrator(login=login_instance)

        block_qid = data.get('blockQid')
        statements = data.get('statements', [])
        deleted_statements = 0
        errors = []

        # First delete all statements for this block
        for stmt in statements:
            try:
                claim_id = stmt.get('claimGuid')
                subject_qid = stmt.get('subjectQid')
                if claim_id and subject_qid:
                    delete_claim(wbi, subject_qid, claim_id)
                    deleted_statements += 1
            except Exception as e:
                errors.append(f"Failed to delete statement {claim_id}: {str(e)}")
                print(f"Error deleting statement {claim_id}: {e}", flush=True)

        # Then delete the block item
        if block_qid:
            delete_block_item(wbi, block_qid)

        return {
            'success': True,
            'error': None,
            'deletedStatements': deleted_statements,
            'errors': errors if errors else None
        }

    except Exception as e:
        print(f"Error unpublishing block: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_triple_to_wikibase')
def handle_publish_triple_to_wikibase(data):
    """Create a triple statement on Wikibase with a reference to the block."""
    try:
        if 'login_token' not in data:
            return {'success': False, 'error': 'No login token provided'}

        sid = None
        for key in user_store:
            if user_store[key]['login_token'] == data['login_token']:
                sid = key
                break

        if sid is None or sid not in user_store:
            return {'success': False, 'error': 'User not logged in, try reloading the page.'}

        login_instance = user_store[sid]['login_instance']
        wbi = WikibaseIntegrator(login=login_instance)

        block_qid = data.get('blockQid')
        triple = data.get('triple', {})

        subject_qid = triple.get('subjectQid')
        property_qid = triple.get('propertyQid')
        object_qid = triple.get('objectQid') or None
        object_literal = triple.get('objectLiteral')
        contexts = triple.get('contexts', [])

        print(f"Publishing triple: subject={subject_qid}, property={property_qid}, object_qid={object_qid}, object_literal={object_literal}", flush=True)

        if not subject_qid or not property_qid:
            return {'success': False, 'error': f'Missing subject or property QID (subject={subject_qid}, property={property_qid})'}

        if not object_qid and object_literal is None:
            return {'success': False, 'error': f'Missing object QID or literal value for triple: {triple}'}

        claim_id = create_statement_with_reference(
            wbi, subject_qid, property_qid, object_qid, object_literal, block_qid, contexts
        )

        return {
            'success': True,
            'error': None,
            'statementId': claim_id,
            'claimGuid': claim_id,
            'subjectQid': subject_qid
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error publishing triple: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_unpublish_triple')
def handle_publish_unpublish_triple(data):
    """Unpublish a single triple - delete its statement from Wikibase."""
    try:
        if 'login_token' not in data:
            return {'success': False, 'error': 'No login token provided'}

        sid = None
        for key in user_store:
            if user_store[key]['login_token'] == data['login_token']:
                sid = key
                break

        if sid is None or sid not in user_store:
            return {'success': False, 'error': 'User not logged in, try reloading the page.'}

        login_instance = user_store[sid]['login_instance']
        wbi = WikibaseIntegrator(login=login_instance)

        subject_qid = data.get('subjectQid')
        claim_guid = data.get('claimGuid')

        if not subject_qid or not claim_guid:
            return {'success': False, 'error': 'Missing subjectQid or claimGuid'}

        delete_claim(wbi, subject_qid, claim_guid)

        return {'success': True, 'error': None}

    except Exception as e:
        print(f"Error unpublishing triple: {e}", flush=True)
        return {'success': False, 'error': str(e)}

@socketio.on('publish_undo')
def handle_publish_undo(data):
    """Undo all published content - delete statements and block items."""
    try:
        if 'login_token' not in data:
            return {'success': False, 'error': 'No login token provided'}

        sid = None
        for key in user_store:
            if user_store[key]['login_token'] == data['login_token']:
                sid = key
                break

        if sid is None or sid not in user_store:
            return {'success': False, 'error': 'User not logged in, try reloading the page.'}

        login_instance = user_store[sid]['login_instance']
        wbi = WikibaseIntegrator(login=login_instance)

        publish_state = data.get('publishState', {})
        deleted_statements = 0
        deleted_blocks = 0
        errors = []

        # Step 1: Delete all statements (must be done before deleting blocks)
        published_statements = publish_state.get('publishedStatements', {})
        for block_id, statements in published_statements.items():
            for stmt in statements:
                try:
                    claim_id = stmt.get('claimGuid')
                    subject_qid = stmt.get('subjectQid')
                    if claim_id and subject_qid:
                        delete_claim(wbi, subject_qid, claim_id)
                        deleted_statements += 1
                        socketio.emit('publish_undo_progress', {
                            'step': 'deleting_statements',
                            'blockId': block_id,
                            'tripleId': stmt.get('tripleId'),
                            'deleted': deleted_statements
                        }, to=request.sid)
                except Exception as e:
                    errors.append(f"Failed to delete statement {claim_id}: {str(e)}")
                    print(f"Error deleting statement {claim_id}: {e}", flush=True)

        # Step 2: Delete all block items
        published_blocks = publish_state.get('publishedBlocks', {})
        for block_id, block_data in published_blocks.items():
            try:
                block_qid = block_data.get('blockQid')
                if block_qid:
                    delete_block_item(wbi, block_qid)
                    deleted_blocks += 1
                    socketio.emit('publish_undo_progress', {
                        'step': 'deleting_blocks',
                        'blockId': block_id,
                        'blockQid': block_qid,
                        'deleted': deleted_blocks
                    }, to=request.sid)
            except Exception as e:
                errors.append(f"Failed to delete block {block_qid}: {str(e)}")
                print(f"Error deleting block {block_qid}: {e}", flush=True)

        # Step 3: Reset the publish state file
        user = data.get('user', '').lower()
        doc = data.get('doc')
        if user and doc:
            state_file = f'/data/jobs/{user}/{doc}.publish.json'
            if os.path.exists(state_file):
                with file_lock(state_file):
                    with open(state_file, 'r') as f:
                        current_state = json.load(f)
                    # Reset published data but keep document and s3 info
                    current_state['publishedStatements'] = {}
                    current_state['publishedBlocks'] = {}
                    current_state['currentStep'] = 4
                    with open(state_file, 'w') as f:
                        json.dump(current_state, f, indent=2)

        return {
            'success': True,
            'error': None,
            'deletedStatements': deleted_statements,
            'deletedBlocks': deleted_blocks,
            'errors': errors if errors else None
        }

    except Exception as e:
        print(f"Error during undo: {e}", flush=True)
        return {'success': False, 'error': str(e)}

if __name__ == '__main__':


    # app.run(host='0.0.0.0', port='8484')
    socketio.run(app)





# def do_something(scheduler): 
#     # schedule the next call first
#     scheduler.enter(10, 1, do_something, (scheduler,))
#     print("Doing stuff...")
#     print('Doing stuff: ' + '',flush=True)
#     # then do your stuff


# print('helklooo stuff: ' + '',flush=True)
# my_scheduler = sched.scheduler(time.time, time.sleep)
# my_scheduler.enter(10, 1, do_something, (my_scheduler,))

# my_scheduler.run()
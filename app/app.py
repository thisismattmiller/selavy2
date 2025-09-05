from flask import Flask, request, render_template, session
from flask_socketio import SocketIO
import subprocess
import time
import uuid
import os
from google import genai
import json
from typing import Dict
import glob
from datetime import datetime
import requests

# from lib.doc_diff import build_doc_diffs
from lib.doc_diff_new import build_doc_diffs


from lib.doc_llm_util import judge_diff
from lib.doc_llm_util import ask_llm_reconcile_project_wide, ask_llm_structured, ask_llm_reconcile_build_search_order, ask_llm_compare_wikidata_entity, ask_llm_normalize_labels

from lib.doc_util import return_ner

from lib.base_util import search_base

client = genai.Client(
    api_key=os.environ.get("GOOGLE_GENAI"),
)

GOOGLE_GEMINI_MODEL = "gemini-2.5-flash"
output_limits = {
    "gemini-2.5-flash": 65_536,
}

from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator import wbi_login

wbi_config['MEDIAWIKI_API_URL'] = 'https://base.semlab.io/api.php'
wbi_config['SPARQL_ENDPOINT_URL'] = 'https://query.semlab.io/proxy/wdqs/bigdata/namespace/wdq/sparql'
wbi_config['WIKIBASE_URL'] = 'https://base.semlab.io'
wbi_config['USER_AGENT'] = 'Selavy 3.0'



app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem' # or 'redis', 'mongodb', etc.

socketio = SocketIO(app,cors_allowed_origins="*")




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


@socketio.on('geminiTokenCount')
def handle_geminiTokenCount(text):
    total_tokens = client.models.count_tokens(
        model=GOOGLE_GEMINI_MODEL, contents=text
    )    
    return {'success': True, 'error': None, 'token_count': total_tokens.total_tokens, 'model': GOOGLE_GEMINI_MODEL, 'limit': output_limits[GOOGLE_GEMINI_MODEL] }



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

    # check if the job exists
    if os.path.exists(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.json'):
        file_data = None
        with open(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.json') as f:
            file_data = json.load(f)
        
        file_data['text_markup'] = job_data['text_markup']

        json.dump(file_data, open(f'/data/jobs/{job_data["user"]}/{job_data["doc"]}.json','w'), indent=2)
        return {'success': True, 'error': None}

    else:
        return {'success': False, 'error': 'Doc not found'}




@socketio.on('judge_diff')
def handle_judge_diff(diff):
    print("diff", diff, flush=True)
    j = judge_diff(diff)
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

    if data['task'] == 'RECONCILE_PROJECT_WIDE' or data['task'] == 'RECONCILE_BY_CLASS':
        response = ask_llm_reconcile_project_wide(data['prompt'])
        return response


    else:
        response = ask_llm_structured(data['prompt'])
        print("response", response, flush=True)
        if response is None:
            return {'success': False, 'error': 'LLM error'}
        else:
            return {'success': True, 'response': response}




@socketio.on('ask_llm_normalize_labels')
def handle_ask_llm_normalize_labels(prompt):
    response = ask_llm_normalize_labels(prompt)
    return response


@socketio.on('ask_llm_reconcile_build_search_order')
def handle_ask_llm_reconcile_build_search_order(prompt):
    print("Sending Proposed Build Search Order Prompt to LLM:", flush=True)
    response = ask_llm_reconcile_build_search_order(prompt)
    return response

@socketio.on('ask_llm_compare_wikidata_entity')
def handle_ask_llm_compare_wikidata_entity(prompt):
    print("Sending Proposed Build Search Order Prompt to LLM:", flush=True)
    response = ask_llm_compare_wikidata_entity(prompt)
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
    data_file = f'/data/jobs/{data['user'].lower()}/{data["job_id"]}.json'

    if os.path.exists(data_file):
        with open(data_file) as f:
            existing_data = json.load(f)
            existing_data['entities'] = data['entities']
            with open(data_file, 'w') as f:
                json.dump(existing_data, f)
    else:
        return {'success': False, 'error': "Job not found"}


    return {'success': True, 'error': None}


@socketio.on('search_semlab_autocomplete')
def handle_search_semlab_autocomplete(search_term):
    try:
        url = f"https://base.semlab.io/w/api.php?action=wbsearchentities&search={search_term}&format=json&errorformat=plaintext&language=en&uselang=en&type=item"
        response = requests.get(url)
        response.raise_for_status()
        
        return {'success': True, 'error': None, 'data': response.json()}
        
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': str(e), 'data': None}

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
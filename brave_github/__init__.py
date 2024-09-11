from flask import Flask, request, render_template, redirect, url_for
import requests
import openai
import os
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

WEBFLOW_API_KEY = os.getenv("WEBFLOW_API_KEY")
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")
GITHUB_API_URL = "https://api.github.com/repos/"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "token")
USE_OPENAI_ENHANCED_DATA = (os.getenv("USE_OPENAI_ENHANCED_DATA", "false").strip().lower() == "true")


def get_repo_data(repo_url):
    parts = repo_url.split('/')
    owner, repo = parts[-2], parts[-1]

    response = requests.get(f"{GITHUB_API_URL}{owner}/{repo}", headers={
        'Authorization': f'token {GITHUB_TOKEN}'
    })

    if response.status_code == 200:
        data = response.json()
        repo_info = {
            "title": data.get("name", "Not specified"),
            "category": "Not specified",
            "description": data.get("description", "No description available"),
            "author": data.get("owner", {}).get("login", "Unknown"),
            "country": "Not specified",
            "language": data.get("language", "Not specified"),
            "license": data.get("license", {}).get("name", "Not specified") if data.get("license") else "No license",
            "github": repo_url,
            "stars": data.get("stargazers_count", 0),
            "created": data.get("created_at", "Unknown").split('T')[0],
            "last_update": data.get("updated_at", "Unknown").split('T')[0]
        }
        return repo_info
    else:
        raise Exception(f"Repository not found or invalid URL: {repo_url}, {str(response)}")

def generate_enhanced_description(repo_data):
    output = None
    if USE_OPENAI_ENHANCED_DATA:
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Given the following information about a GitHub repository, provide a more detailed and compelling description, and suggest a possible LinkedIn URL for the author:\n\n" \
                                        f"Title: {repo_data['title']}\n" \
                                        f"Description: {repo_data['description']}\n" \
                                        f"Author: {repo_data['author']}\n" \
                                        f"Language: {repo_data['language']}\n" \
                                        f"License: {repo_data['license']}\n\n" \
                                        f"Better Description and LinkedIn URL:"}
        ]
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=150,
            temperature=0.7,
        )
        
        output = response['choices'][0]['message']['content'].strip()
    return output

def add_to_webflow_collection(repo_data):
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_KEY}",
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    created_year = datetime.strptime(repo_data["created"], "%Y-%m-%d").year
    last_update_year = datetime.strptime(repo_data["last_update"], "%Y-%m-%d").year

    item_data = {
        "fieldData": {
            "name": repo_data["title"],  # Ensure this matches your collection's field name
            "slug": repo_data["title"].lower().replace(" ", "-"),  # Ensure the slug is unique
            "founder-full-name": repo_data["author"],  # Adjust this field name as necessary
            "description": repo_data["description"],  # Adjust this field name as necessary
            "github": repo_data["github"],  # Adjust this field name as necessary
            "language": repo_data["language"],  # Adjust this field name as necessary
            "license": repo_data["license"],  # Adjust this field name as necessary
            "stars": repo_data["github_stars"],  # Adjust this field name as necessary
            "created": created_year,
            "last-update": last_update_year
        },
        "isArchived": False,
        "isDraft": False
    }

    response = requests.post(url, headers=headers, json=item_data)
    return response.json()


@app.route('/', methods=['GET', 'POST'])
def index():
    repo_url = request.args.get('url', '')  # Get the 'url' parameter from the GET request
    
    repo_data = None
    webflow_response = None
    if request.method == 'POST':
       
        if 'repo_url' in request.form:
            repo_url = request.form.get('repo_url')
            repo_data = get_repo_data(repo_url)
            
            if 'error' not in repo_data and USE_OPENAI_ENHANCED_DATA:
                enhanced_description = generate_enhanced_description(repo_data)
                repo_data['enhanced_description'] = enhanced_description

        if 'add_to_webflow' in request.form:
            repo_url = request.form.get('repo_url')
            repo_data = {
                'title': request.form.get('title'),
                'description': request.form.get('description'),
                'author': request.form.get('author'),
                'language': request.form.get('language'),
                'license': request.form.get('license'),
                'github': repo_url,
                'github_stars': request.form.get('github_stars'),
                'created': request.form.get('created'),
                'last_update': request.form.get('last_update')
            }
            webflow_response = add_to_webflow_collection(repo_data)
    
    return render_template('index.html', 
                           repo_data=repo_data, 
                           repo_url=repo_url, 
                           webflow_response=webflow_response, 
                           conf={'use_openai': USE_OPENAI_ENHANCED_DATA})

if __name__ == "__main__":
    app.run(debug=True)
# app.py (Professional UI with server-side key)
# app.py

import os # <-- ADD THIS LINE
from flask import Flask, render_template, request, jsonify
# ... other imports ...
from flask import Flask, render_template, request, jsonify
import praw
from prawcore.exceptions import NotFound, PrawcoreException
import requests

# --- YOUR CREDENTIALS ---
# --- Securely get credentials from environment variables ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
USER_AGENT = os.getenv("USER_AGENT", "MyWebAppSummarizer v2.0") # We can add a default here
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ... The rest of your app.py code remains exactly the same ...
app = Flask(__name__)

# --- Helper Functions (Backend Logic) ---

def fetch_user_comments(username, limit=1000):
    try:
        reddit = praw.Reddit(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, user_agent=USER_AGENT)
        user = reddit.redditor(username)
        _ = user.created_utc
        return [comment.body for comment in user.comments.new(limit=limit)]
    except NotFound:
        raise ValueError(f"Reddit user '{username}' not found.")
    except PrawcoreException as e:
        raise ValueError(f"Could not connect to Reddit. Details: {e}")
    except Exception as e:
        raise ConnectionError(f"An unexpected error occurred while fetching comments: {e}")

def get_ai_summary(text_to_summarize, user_prompt):
    try:
        api_url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        data_payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"""{user_prompt}\n\nHere is the text to analyze:\n---\n{text_to_summarize}"""}
            ]
        }
        response = requests.post(api_url, headers=headers, json=data_payload, timeout=90)
        response.raise_for_status()
        summary = response.json()['choices'][0]['message']['content']
        return summary
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise ValueError("Authentication with AI API failed. The server's API Key is invalid.")
        raise ConnectionError(f"The AI API returned an error: {e.response.status_code} {e.response.text}")
    except Exception as e:
        raise ConnectionError(f"An unexpected error occurred while contacting the AI API: {e}")

# --- API Endpoints ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_comments', methods=['POST'])
def handle_fetch_comments():
    try:
        username = request.json.get('username')
        if not username:
            raise ValueError("Reddit username is required.")
        
        comments = fetch_user_comments(username)
        if not comments:
            return jsonify({'error': 'This user has no recent comments to analyze.'}), 404
        
        full_text = "\n\n---\n\n".join(comments)
        return jsonify({'comments_text': full_text, 'comment_count': len(comments)})
    except (ValueError, ConnectionError) as e:
        return jsonify({'error': str(e)}), 400

@app.route('/get_summary', methods=['POST'])
def handle_get_summary():
    try:
        data = request.json
        comments_text = data.get('comments_text')
        prompt = data.get('prompt')

        summary = get_ai_summary(comments_text, prompt) # Key is no longer needed here
        return jsonify({'summary': summary})
    except (ValueError, ConnectionError) as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
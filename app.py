# app.py (with Diagnostic Printing)

import os
from flask import Flask, render_template, request, jsonify
import praw
from prawcore.exceptions import NotFound, PrawcoreException
import requests

# --- Securely get credentials from environment variables ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
USER_AGENT = os.getenv("USER_AGENT")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ===================================================================
#  VVV NEW DIAGNOSTIC CODE VVV
# ===================================================================
print("--- LAUNCHING SERVER: CHECKING ENVIRONMENT VARIABLES ---")
# This will print to the Render logs when the server starts.
if CLIENT_ID:
    print(f"✅ CLIENT_ID loaded. Starts with: {CLIENT_ID[:5]}")
else:
    print("❌ ERROR: CLIENT_ID environment variable not found!")

if CLIENT_SECRET:
    print(f"✅ CLIENT_SECRET loaded. Starts with: {CLIENT_SECRET[:5]}")
else:
    print("❌ ERROR: CLIENT_SECRET environment variable not found!")

if OPENROUTER_API_KEY:
    print(f"✅ OPENROUTER_API_KEY loaded. Starts with: {OPENROUTER_API_KEY[:5]}")
else:
    print("❌ ERROR: OPENROUTER_API_KEY environment variable not found!")
print("----------------------------------------------------")
# ===================================================================

# --- The rest of the code is unchanged ---

app = Flask(__name__)

# ... (The rest of your app.py file remains exactly the same) ...

# --- Helper Functions (Backend Logic) ---

def fetch_user_comments(username, limit=100):
    try:
        # Check if keys were loaded
        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError("Reddit API credentials are not configured on the server.")
            
        reddit = praw.Reddit(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, user_agent=USER_AGENT)
        user = reddit.redditor(username)
        _ = user.created_utc
        return [comment.body for comment in user.comments.new(limit=limit)]
    except NotFound:
        raise ValueError(f"Reddit user '{username}' not found.")
    except PrawcoreException as e:
        # Re-raise with a clearer message
        raise ValueError(f"Could not connect to Reddit. This is likely an invalid CLIENT_ID or CLIENT_SECRET. Details: {e}")
    except Exception as e:
        raise ConnectionError(f"An unexpected error occurred while fetching comments: {e}")

# ... (the rest of your get_ai_summary and route functions are the same) ...
# (The code is omitted here for brevity, just copy the whole block from this message)

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
        # ... (rest of this function is the same)
        comments_text = data.get('comments_text')
        prompt = data.get('prompt')

        # Add a check here for the AI key
        if not OPENROUTER_API_KEY:
            raise ValueError("The server's AI API Key is not configured.")

        summary = get_ai_summary(comments_text, prompt)
        return jsonify({'summary': summary})
    except (ValueError, ConnectionError) as e:
        return jsonify({'error': str(e)}), 400

def get_ai_summary(text_to_summarize, user_prompt):
    # This function is unchanged
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

if __name__ == '__main__':
    app.run(debug=True)
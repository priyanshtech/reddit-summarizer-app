# app.py

import os
from flask import Flask, render_template, request, jsonify
import praw
from prawcore.exceptions import NotFound, PrawcoreException
import requests

# --- Load credentials from environment variables ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
USER_AGENT = os.getenv("USER_AGENT")
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")

# --- Initialize the Flask App ---
app = Flask(__name__)

# --- Helper Functions (Backend Logic) ---

def fetch_user_comments(username, limit=100):
    """Fetches comments from a Reddit user using safe, read-only mode."""
    try:
        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError("Reddit API credentials are not configured on the server.")
            
        reddit = praw.Reddit(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, user_agent=USER_AGENT)
        user = reddit.redditor(username)
        _ = user.created_utc
        return [comment.body for comment in user.comments.new(limit=limit)]
    except NotFound:
        raise ValueError(f"Reddit user '{username}' not found.")
    except PrawcoreException as e:
        raise ValueError(f"Could not connect to Reddit. This is likely an invalid CLIENT_ID or CLIENT_SECRET. Details: {e}")
    except Exception as e:
        raise ConnectionError(f"An unexpected error occurred while fetching comments: {e}")


def get_ai_summary(text_to_summarize, user_prompt):
    """Sends a block of text and a custom prompt to the Google AI Gemini API."""
    try:
        if not GOOGLE_AI_API_KEY:
            raise ValueError("The server's GOOGLE_AI_API_KEY is not configured.")

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GOOGLE_AI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        full_prompt = f"""{user_prompt}\n\nHere is the user's writing sample from Reddit to analyze:\n---\n{text_to_summarize}"""
        
        data_payload = {
            "contents": [{"parts": [{"text": full_prompt}]}]
        }
        
        response = requests.post(api_url, headers=headers, json=data_payload, timeout=90)
        response.raise_for_status()
        response_json = response.json()
        
        if 'candidates' not in response_json or not response_json['candidates']:
             raise ValueError("The AI model generated an empty response, possibly due to a safety filter.")

        summary = response_json['candidates'][0]['content']['parts'][0]['text']
        return summary.strip()

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            raise ValueError("Authentication with Google AI failed. The GOOGLE_AI_API_KEY is likely invalid.")
        raise ConnectionError(f"The Google AI API returned an error: {e.response.status_code}. Response: {e.response.text}")
    except Exception as e:
        raise ConnectionError(f"An unexpected error occurred while contacting the Google AI API: {e}")


# --- API Endpoints (Routes for the website) ---

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
        summary = get_ai_summary(comments_text, prompt)
        return jsonify({'summary': summary})
    except (ValueError, ConnectionError) as e:
        return jsonify({'error': str(e)}), 400

# --- Start the Server ---
if __name__ == '__main__':
    app.run(debug=True)
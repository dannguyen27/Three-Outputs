from flask import Flask, render_template, request, jsonify
import openai
import os
import time
import requests
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
from ratelimit import limits, sleep_and_retry
import logging

logging.basicConfig(level=logging.INFO)

ONE_MINUTE = 60

# Load your API keys from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
UNSPLASH_API_KEY = os.getenv("UNSPLASH_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

app = Flask(__name__)

# Initialize Spotipy with client credentials
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

@sleep_and_retry
@limits(calls=20, period=ONE_MINUTE)
def generate_story_text(user_input, temperature):
    try:
        story_prompt = f"Write a detailed and creative short story based on the theme: {user_input}. Make sure the story has a clear ending and is cohesive and flowing."
        story_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": story_prompt}],
            max_tokens=500,  # Increase max tokens to give more space for completion
            temperature=temperature
        )
        story = story_response['choices'][0]['message']['content'].strip()

        # Check if the story seems to end mid-sentence
        if not story.endswith(('.', '!', '?', '"')):
            # Add a follow-up prompt to complete the sentence
            followup_prompt = f"Continue and conclude the following story: {story}"
            followup_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": followup_prompt}],
                max_tokens=50,  # Smaller token limit for just finishing the story
                temperature=temperature
            )
            followup_text = followup_response['choices'][0]['message']['content'].strip()
            story += " " + followup_text

        return story
    except openai.error.RateLimitError:
        logging.error("Rate limit exceeded. Waiting for 60 seconds...")
        time.sleep(60)
        return generate_story_text(user_input, temperature)


def fetch_unsplash_image(query):
    url = f"https://api.unsplash.com/photos/random?query={query}&client_id={UNSPLASH_API_KEY}&orientation=landscape"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        image_url = data['urls']['regular']  # or 'small', 'full', depending on your needs
        return image_url
    else:
        logging.error(f"Failed to fetch image from Unsplash. Status code: {response.status_code}")
        return None

def fetch_spotify_track(query):
    results = spotify.search(q=query, type='track', limit=1)

    if results['tracks']['items']:
        track = results['tracks']['items'][0]
        return track['uri']
    else:
        logging.error("No suitable track found for query.")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_story', methods=['POST'])
def generate_story():
    data = request.get_json()
    user_input = data.get('story_prompt')
    temperature = float(data.get('temperature', 0.7))

    try:
        story = generate_story_text(user_input, temperature)
        image_url = fetch_unsplash_image(user_input)
        spotify_uri = fetch_spotify_track(user_input)

        return jsonify({'story': story, 'image_url': image_url, 'spotify_uri': spotify_uri})
    except openai.error.InvalidRequestError:
        logging.error("API quota exceeded.")
        return jsonify({'error': 'API quota exceeded. Please try again later.'}), 429
    except requests.RequestException as e:
        logging.error(f"Failed to fetch image or song: {str(e)}")
        return jsonify({'story': story, 'error': 'Failed to fetch image or song.'}), 500

if __name__ == '__main__':
    app.run(debug=True)

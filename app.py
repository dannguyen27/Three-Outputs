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
def generate_story_text_and_queries(user_input, temperature):
    try:
        # Generate the story
        story_prompt = f"Write a detailed and creative short story based on the theme: {user_input}. Make sure the story has a clear ending and is cohesive and flowing."
        story_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": story_prompt}],
            max_tokens=500,
            temperature=temperature
        )
        story = story_response['choices'][0]['message']['content'].strip()

        # Generate a query for the Unsplash image
        image_query_prompt = f"Based on the following story, generate a general query to find an appropriate image, 3 words max: {story}"
        image_query_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": image_query_prompt}],
            max_tokens=50,
            temperature=temperature
        )
        image_query = image_query_response['choices'][0]['message']['content'].strip()
        logging.info(f"Generated image query: {image_query}")

        # Generate a query for the Spotify song
        song_query_prompt = f"Based on the following story, describe the type of song (including mood, genre, and any themes) that would be most suitable as a soundtrack: {story}"
        song_query_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": song_query_prompt}],
            max_tokens=50,
            temperature=temperature
        )
        song_query = song_query_response['choices'][0]['message']['content'].strip()

        # Further simplify the query
        simplify_query_prompt = f"Simplify the following query to be used as a search term for finding a song on Spotify: {song_query}"
        simplified_query_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": simplify_query_prompt}],
            max_tokens=20,
            temperature=temperature
        )
        simplified_song_query = simplified_query_response['choices'][0]['message']['content'].strip()

        

        return story, image_query, simplified_song_query
    except openai.error.RateLimitError:
        print("Rate limit exceeded. Waiting for 60 seconds...")
        time.sleep(60)
        return generate_story_text_and_queries(user_input, temperature)



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
    try:
        results = spotify.search(q=query, type='track', limit=1)
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            return track['uri']
        else:
            logging.error("No suitable track found for query.")
            return None
    except spotipy.exceptions.SpotifyException as e:
        logging.error(f"Spotify search failed with error: {e}")
        return None  # Or return a default song URI if you have one

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_story', methods=['POST'])
def generate_story():
    data = request.get_json()  # Parse JSON data
    user_input = data.get('story_prompt')
    temperature = float(data.get('temperature', 0.7))  # Default to 0.7 if not provided

    try:
        # Generate the story, image query, and song query using GPT
        story, image_query, song_query = generate_story_text_and_queries(user_input, temperature)

        # Fetch an image from Unsplash based on the GPT-generated image query
        image_url = fetch_unsplash_image(image_query)

        # Fetch a song from Spotify based on the GPT-generated song query
        spotify_uri = fetch_spotify_track(song_query)

        return jsonify({'story': story, 'image_url': image_url, 'spotify_uri': spotify_uri})
    except openai.error.InvalidRequestError as e:
        return jsonify({'error': 'API quota exceeded. Please try again later.'}), 429
    except requests.RequestException as e:
        return jsonify({'story': story, 'error': 'Failed to fetch image or song.'}), 500

if __name__ == '__main__':
    app.run(debug=True)

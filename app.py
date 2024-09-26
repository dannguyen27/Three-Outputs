from flask import Flask, render_template, request, jsonify
import openai
import os
import time
from ratelimit import limits, sleep_and_retry
import logging
logging.basicConfig(level=logging.INFO)

ONE_MINUTE = 60

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

# Load your OpenAI API key
openai.api_key = OPENAI_API_KEY

# Rate limiting function
@sleep_and_retry
@limits(calls=20, period=ONE_MINUTE)
def generate_story_text(user_input):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"Create a short story based on this theme: {user_input}"}],
            max_tokens=150
        )
        story = response['choices'][0]['message']['content']
        return story
    except openai.error.RateLimitError:
        print("Rate limit exceeded. Waiting for 60 seconds...")
        time.sleep(60)
        return generate_story_text(user_input)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_story', methods=['POST'])
def generate_story():
    user_input = request.form['story_prompt']
    try:
        story = generate_story_text(user_input)
        return jsonify({'story': story})
    except openai.error.InvalidRequestError as e:
        return jsonify({'error': 'API quota exceeded. Please try again later.'}), 429


if __name__ == '__main__':
    app.run(debug=True)

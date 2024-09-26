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
def generate_story_text(user_input, temperature):
    try:
        # Directly prompt for a cohesive story
        story_prompt = f"Write a detailed and creative short story based on the theme: {user_input}. Make the narrative cohesive and flowing."
        story_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": story_prompt}],
            max_tokens=400,  # You can adjust the max tokens to allow for a longer story
            temperature=temperature  # Use the user-selected temperature
        )
        story = story_response['choices'][0]['message']['content'].strip()
        return story
    except openai.error.RateLimitError:
        print("Rate limit exceeded. Waiting for 60 seconds...")
        time.sleep(60)
        return generate_story_text(user_input, temperature)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_story', methods=['POST'])
def generate_story():
    user_input = request.form['story_prompt']
    temperature = float(request.form.get('temperature', 0.8))  # Default to 0.8 if not provided
    try:
        story = generate_story_text(user_input, temperature)
        return jsonify({'story': story})
    except openai.error.InvalidRequestError as e:
        return jsonify({'error': 'API quota exceeded. Please try again later.'}), 429


if __name__ == '__main__':
    app.run(debug=True)

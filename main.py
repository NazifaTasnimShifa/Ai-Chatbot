from flask import Flask, render_template, request, jsonify, send_from_directory
import json
import requests
import random
import string
import re
import os
import spacy

# === Flask setup ===
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# === Load spaCy large model ===
nlp = spacy.load("en_core_web_lg")

# === Helper functions ===
def load_intents(file_path):
    if not os.path.exists(file_path):
        return {"intents": []}
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_intents(intents, file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(intents, file, indent=4)

def generate_tag(user_input):
    cleaned_input = re.sub(r'[^\w\s]', '', user_input.lower())
    stopwords = ['in', 'of', 'the', 'and', 'for', 'on', 'at', 'to', 'a', 'an']
    cleaned_input = ' '.join(word for word in cleaned_input.split() if word not in stopwords)
    return cleaned_input.replace(' ', '_')

def get_random_response(intent):
    return random.choice(intent['responses'])

def get_response(intents, query, threshold=0.75):
    """Find best matching intent using spaCy similarity."""
    user_doc = nlp(query)
    best_intent = None
    best_score = 0.0

    for intent in intents['intents']:
        for pattern in intent['patterns']:
            pattern_doc = nlp(pattern)
            if user_doc.vector_norm and pattern_doc.vector_norm:
                score = user_doc.similarity(pattern_doc)
            else:
                score = 0
            if score > best_score:
                best_intent = intent
                best_score = score

    if best_intent and best_score >= threshold:
        response = get_random_response(best_intent)
        return response.get('text'), response.get('link')
    return None, None

def capture_conversation(intents, user_input=None, response=None, link=None):
    if user_input and response:
        new_tag = generate_tag(user_input)
        if not any(intent['patterns'][0].lower() == user_input.lower() for intent in intents['intents']):
            intent = {
                'tag': new_tag,
                'patterns': [user_input],
                'responses': [{'text': response, 'link': link}]
            }
            intents['intents'].append(intent)
            save_intents(intents, 'intents.json')
            print("Saved new intent:", user_input, "->", response)

def search(query):
    """Google Custom Search fallback"""
    url = "https://www.googleapis.com/customsearch/v1"
    api_key = "AIzaSyBQdKT44VwjzJtJ4Adq64QqKD3P6wWQSWg"   # ✅ your working key
    cx = "a48bea04ec2654658"                              # ✅ your custom search engine id
    params = {"key": api_key, "cx": cx, "q": query}

    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get("items"):
            result = data["items"][0]["snippet"]
            link = data["items"][0]["link"]
            return result, link
    except Exception as e:
        print("Search error:", e)
    return None, None

# === Routes ===
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.form['user_input']
    intents = load_intents('intents.json')

    if user_input.lower() == "exit":
        capture_conversation(intents)
        return jsonify({'response': 'Goodbye!'})

    # Try matching using spaCy semantic similarity
    text_response, link_response = get_response(intents, user_input)

    if text_response:
        if link_response:
            response_message = f"{text_response}<br><a href='{link_response}' target='_blank'>More Details</a>"
        else:
            response_message = text_response
        capture_conversation(intents, user_input, text_response, link_response)
        return jsonify({'response': response_message})

    # If no intent found, use Google search
    result, link = search(user_input)
    if result and link:
        capture_conversation(intents, user_input, result, link)
        # ✅ Return keys exactly like your JS expects
        return jsonify({'result': result, 'link': link})

    # No results found
    return jsonify({'response': "Sorry, I couldn't find an answer."})

@app.route('/save', methods=['POST'])
def save():
    intents = load_intents('intents.json')
    capture_conversation(intents)
    return jsonify({'saved': True})

@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)

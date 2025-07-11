from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from typing import Dict, Any

from main import graph  # your full code above is in this file
from langgraph.checkpoint.memory import MemorySaver

app = Flask(__name__, static_folder="frontend")
CORS(app)

memory = MemorySaver()
config = {"configurable":{"thread_id":"1"}}

# Serve the main page (index.html) at the root URL
@app.route("/")
def serve_index():
    return send_from_directory("frontend", "index.html")

# Serve any other frontend static files (JS, CSS, images, etc.)
@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("frontend", path)

# Your existing chat endpoint for POST requests
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    user_input = data.get("message", "")
    neighborhood = data.get("neighborhood", None)

    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    try:
        # Inject neighborhood context
        if neighborhood:
            system_message = {
                "role": "system",
                "content": f"The user is asking about the neighborhood: {neighborhood}. Use this as context."
            }
            messages = [system_message, {"role": "user", "content": f"In {neighborhood} ," + user_input}]
        else:
            messages = [{"role": "user", "content": user_input}]

        response = graph.invoke({"messages": messages}, config=config)

        for m in response['messages']:
            m.pretty_print()

        # Find last assistant message
        final_message = None
        for m in reversed(response['messages']):
            if hasattr(m, 'content') and m.content:
                final_message = m.content.strip()
                break

        if final_message:
            return jsonify({"messages": [final_message]})
        else:
            return jsonify({"messages": ["Sorry, I couldn't find a response."]})

    except Exception as e:
        return jsonify({"error": f"Error processing request: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
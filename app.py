from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from typing import Dict, Any

# from main import graph  # your full code above is in this file
from langgraph.checkpoint.memory import MemorySaver
import uuid
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
# from main import graph
from langchain.agents import initialize_agent
from langchain.agents.agent_types import AgentType
from main import jeonse_agent_tool, home_agent_tool, generate_chart_tool, build_agent_graph


load_dotenv()


llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4.1-mini")

app = Flask(__name__, static_folder="frontend")
CORS(app)

UPLOAD_DIR = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
user_csv_path = None
user_csv_agent_tool = None

memory = MemorySaver()
config = {"configurable":{"thread_id":"1"}}


@app.route("/upload", methods=["POST"])
def upload_csv():
    global user_csv_path, user_csv_agent_tool

    if 'file' not in request.files:
        return "No file part", 400
    f = request.files['file']
    if f.filename == '':
        return "No selected file", 400

    # secure and unique filename
    fname = secure_filename(f.filename)
    unique_name = f"{uuid.uuid4().hex}_{fname}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    f.save(save_path)
    user_csv_path = save_path

    # instantiate a new CSV agent on this file
    from langchain_experimental.agents.agent_toolkits import create_csv_agent
    from langchain.agents.agent_types import AgentType

    user_agent = create_csv_agent(
        llm,
        user_csv_path,
        verbose=True,
        allow_dangerous_code=True,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        agent_executor_kwargs={
            "system_message": (
                "You are analyzing the user-uploaded CSV. "
                "Answer strictly from its contents."
            )
        }
    )
    user_csv_agent_tool = user_agent.as_tool(
        name="user_csv_tool",
        arg_types={"input": str},
        description="Use this to answer questions about the user’s uploaded CSV. ONLY call this if the user specify its about THEIR UPLOADED FILE"
    )

    return "Uploaded", 200

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)


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
    Region = data.get("Region", None)

    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    try:
        # Inject Region context
        if Region:
            system_message = {
                "role": "system",
                "content": f"The user is asking about the Region: {Region}. Use this as context."
            }
            messages = [system_message, {"role": "user", "content": f"In {Region} ," + user_input}]
        else:
            messages = [{"role": "user", "content": user_input}]

        
        tools = [jeonse_agent_tool, home_agent_tool, generate_chart_tool]
        if user_csv_agent_tool:
            tools.append(user_csv_agent_tool)
        graph = build_agent_graph(tools, memory)
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
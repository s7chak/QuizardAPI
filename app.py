from flask import Flask, request, jsonify, session
from flask_cors import CORS
from ops.opapp import Util
from datetime import timedelta
from flask_session import Session

app = Flask(__name__)

@app.route("/getText", methods=["POST"])
def get_text():
    """
        Endpoint to extract text from given links.
        Expects a JSON payload: { "links": ["link1", "link2", ...] }
    """
    try:
        data = request.get_json()
        if not data or "links" not in data:
            return jsonify({"error": "Invalid input. 'links' field is required."}), 400
        links = data["links"]
        if not isinstance(links, list) or not all(isinstance(link, str) for link in links):
            return jsonify({"error": "Invalid 'links'. Must be a list of strings."}), 400
        util = Util()
        util.extract_text(links)
        extracted_text = session[session.sid]['corpus']
        return jsonify({"text": extracted_text}), 200

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/set_data')
def set_data():
    session['user_id'] = 12345  # Set some data
    return 'Data set in session.'

@app.route('/get_data')
def get_data():
    user_id = session.get('user_id', None)  # Get the session data
    return f'User ID: {user_id}'

if __name__ == "__main__":
    app.secret_key = 'quizardapi_sc'
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
    app.config['SESSION_COOKIE_NAME'] = 'quizard_session'
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    CORS(app)
    Session(app)
    app.run(host="0.0.0.0", port=1000)
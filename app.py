import os
import json
from flask import Flask, redirect, request, jsonify
from google_auth_oauthlib.flow import Flow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")

def get_client_config():
    return json.loads(os.environ["GOOGLE_OAUTH_CREDENTIALS"])

@app.route("/")
def start_auth():
    flow = Flow.from_client_config(
        get_client_config(),
        scopes=SCOPES,
        redirect_uri=os.environ["GOOGLE_REDIRECT_URI"]
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    flow = Flow.from_client_config(
        get_client_config(),
        scopes=SCOPES,
        redirect_uri=os.environ["GOOGLE_REDIRECT_URI"]
    )

    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    with open("token.json", "w") as f:
        f.write(creds.to_json())

    from fetch_purchases import fetch_purchase_emails
    result = fetch_purchase_emails()

    from classify_mails import process_mails
    result = process_mails()

    return jsonify(result)


if __name__ == "__main__":
    app.run()



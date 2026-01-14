import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service():
    if not os.path.exists("token.json"):
        raise Exception("token.json not found. OAuth not completed.")

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    return build("gmail", "v1", credentials=creds)

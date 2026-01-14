import json
from base64 import urlsafe_b64decode
from gmail_auth import get_gmail_service


def extract_parts(parts):
    """Recursively extract the email body from nested MIME parts."""
    body = ""

    for part in parts:
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data")

        # If this part has data, decode it
        if data:
            decoded = urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            body += decoded

        # If this part contains more parts, recurse into them
        if "parts" in part:
            body += extract_parts(part["parts"])

    return body


def get_message_body(payload):
    """Extract the full email body (HTML or plaintext, entire content)."""

    # CASE 1 — Email has multiple nested parts
    if "parts" in payload:
        return extract_parts(payload["parts"])

    # CASE 2 — Simple email with single part
    data = payload.get("body", {}).get("data")
    if data:
        return urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return ""


def fetch_purchase_emails():
    service = get_gmail_service()

    # change this to "category:shopping" later
    # subject:(order OR invoice OR purchase OR receipt)
    query = "category:purchases"

    results = service.users().messages().list(
        userId="me", q=query, maxResults=100
    ).execute()

    messages = results.get("messages", [])

    emails = []

    for idx, msg in enumerate(messages):
        full_msg = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()

        payload = full_msg.get("payload", {})

        body = get_message_body(payload)

        # Extract metadata
        headers = payload.get("headers", [])
        metadata = {
            "from": next((h["value"] for h in headers if h["name"] == "From"), None),
            "to": next((h["value"] for h in headers if h["name"] == "To"), None),
            "subject": next((h["value"] for h in headers if h["name"] == "Subject"), None),
            "date": next((h["value"] for h in headers if h["name"] == "Date"), None),
            "id": msg["id"],
        }

        emails.append({
            "index": idx,
            "metadata": metadata,
            "body": body
        })

    # SAVE OUTPUT TO JSON FILE
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(emails, f, indent=4, ensure_ascii=False)

    print("✔ output.json has been generated with full email bodies.")

    return emails


if __name__ == "__main__":
    fetch_purchase_emails()



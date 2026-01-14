import json
import re
from bs4 import BeautifulSoup


# =============================
# Load Brand Database
# =============================

with open("brands.json", "r", encoding="utf-8") as f:
    BRANDS = json.load(f)


# =============================
# Regex Patterns
# =============================

AMOUNT_REGEXES = [
    r"(?:rs\.?|inr|₹)\s*([0-9]{1,3}(?:[, ]?[0-9]{2,3})*(?:\.\d{1,2})?)",
    r"([0-9]{1,3}(?:[, ]?[0-9]{2,3})*(?:\.\d{1,2})?)\s*(?:rs\.?|inr|₹)",
    r"\btotal[: ]*([0-9]{1,3}(?:[, ]?[0-9]{2,3})*(?:\.\d{1,2})?)\b",
    r"\bamount(?: paid| due| charged)?[: ]*([0-9]{1,3}(?:[, ]?[0-9]{2,3})*(?:\.\d{1,2})?)"
]


DATE_REGEX = re.compile(
    r"(\b\d{1,2}[-/ ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-/ ]?\d{2,4}\b|"
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s*\d{4}\b|"
    r"\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b|"
    r"\b\d{4}[-/]\d{2}[-/]\d{2}\b|"
    r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b)",
    re.IGNORECASE
)


ID_REGEX = re.compile(
    r"(order id|transaction id|txn id|utr|folio|invoice number|invoice no)",
    re.IGNORECASE
)


# Receipt metadata keywords
RECEIPT_META = ["invoice", "receipt", "payment", "purchase", "order", "transaction"]

RECURRING_KEYWORDS = [
    "subscription", "renewal", "auto-debit", "recurring", "billing cycle",
    "renews on", "auto-renew"
]

FREQ_PATTERNS = {
    "weekly": [
        r"\bweekly\b",
        r"\bevery week\b",
        r"\bper week\b",
        r"\brenews weekly\b",
        r"\b7 days\b",
        r"/\s*week",
        r"\bwk\b"
    ],
    "monthly": [
        r"\bmonthly\b",
        r"\bevery month\b",
        r"\bper month\b",
        r"\bbilled monthly\b",
        r"\brenews monthly\b",
        r"/\s*mo\b",
        r"/\s*mon\b",
        r"\b30 days\b",
        r"\bevery 30 days\b"
    ],
    "yearly": [
        r"\byearly\b",
        r"\bannual\b",
        r"\bannually\b",
        r"\bper year\b",
        r"\bbilled yearly\b",
        r"\brenews yearly\b",
        r"/\s*yr\b",
        r"/\s*year\b",
        r"\b12 months\b"
    ],
    "quarterly": [
        r"\bquarterly\b",
        r"\bevery 3 months\b",
        r"\b3 months\b"
    ],
    "semi_annual": [
        r"\bsemi[- ]?annual\b",
        r"\bevery 6 months\b",
        r"\b6 months\b"
    ]
}



# ==============================
# Helper Functions
# ==============================

def weighted_brand_match(text, sender, subject):
    """
    Uses brands.json to detect brand with weighted scoring.
    Returns: (brand_name or None, category or 'others')
    """

    best_brand = None
    best_category = "others"
    best_score = 0
    best_priority = -1

    for brand, data in BRANDS.items():

        patterns = data.get("patterns", [])
        senders = data.get("sender_domains", [])
        subjects = data.get("subject_contains", [])
        weights = data.get("score_weights", {"pattern": 0.5, "sender": 0.3, "subject": 0.2})
        priority = data.get("priority", 1)

        score = 0

        # ----------------------------------------------------
        # PATTERN MATCH (strongest signal)
        # ----------------------------------------------------
        for p in patterns:
            try:
                if re.search(p, text, flags=re.IGNORECASE):
                    score += weights.get("pattern", 0.5)
                    break
            except:
                continue

        # ----------------------------------------------------
        # SENDER DOMAIN MATCH
        # ----------------------------------------------------
        sender_lower = sender.lower()
        for d in senders:
            if d.lower() in sender_lower:
                score += weights.get("sender", 0.3)
                break

        # ----------------------------------------------------
        # SUBJECT MATCH
        # ----------------------------------------------------
        subject_lower = subject.lower()
        for s in subjects:
            if s.lower() in subject_lower:
                score += weights.get("subject", 0.2)
                break

        # ----------------------------------------------------
        # PICK BEST BRAND (score + priority fallback)
        # ----------------------------------------------------
        if (score > best_score) or (score == best_score and priority > best_priority):
            best_score = score
            best_priority = priority
            best_brand = brand
            best_category = data["category"]

    # --------------------------------------------------------
    # If the match score is too weak → discard brand
    # --------------------------------------------------------
    if best_score < 0.35:   # threshold to avoid false matches
        return None, "others"

    return best_brand, best_category

def extract_brand_from_sender(sender):
    sender = sender.lower()

    # Extract domain without tld
    match = re.search(r"@([a-z0-9.-]+)\.(com|in|net|org|co)", sender)
    if not match:
        return None

    domain = match.group(1)

    # remove subdomains
    parts = domain.split(".")
    brand = parts[-1]  # last segment = brand-like

    # Remove generic words
    if brand in ["mail", "info", "support", "billing", "noreply", "service"]:
        return None
    
    return brand

def extract_brand_from_text(text):
    # Get capitalized words or sequences like "SBI Mutual Fund"
    matches = re.findall(r"\b([A-Z][A-Za-z0-9& ]+)\b", text)

    if not matches:
        return None

    # remove generic nonsense
    blacklist = ["Dear", "Invoice", "Order", "Payment", "Statement", "Receipt", "Thank", "Regards"]
    matches = [m.strip() for m in matches if m.strip() not in blacklist]

    if not matches:
        return None

    # Best guess is the first capitalized phrase
    return matches[0]

def extract_brand_from_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # Look for alt text in logos
    for img in soup.find_all("img"):
        alt = img.get("alt")
        if alt:
            alt_clean = alt.strip()
            if len(alt_clean.split()) <= 4 and re.search(r"[A-Za-z]", alt_clean):
                return alt_clean

    return None

def normalize_html_amounts(html):
    """
    Fixes split-digit issues in HTML (e.g., <span>3</span><span>0</span><span>0</span><span>0</span> → 3000)
    Removes all tags but keeps text, then joins digit sequences.
    """
    # Remove all HTML tags
    clean = re.sub(r"<[^>]+>", " ", html)

    # Join digits separated by whitespace or styling splits
    clean = re.sub(r"(?<=\d)\s+(?=\d)", "", clean)

    return clean

def is_valid_amount(amt):
    """Strict sanity filter for detected amounts."""
    try:
        amt_float = float(amt)
    except:
        return False

    # Reject single-digit / unrealistic values
    if amt_float < 10:
        return False

    # Reject gigantic values (safety)
    if amt_float > 100000000:
        return False

    return True

def normalize_broken_dates(text):
    """
    Fix cases where month/day and year appear on separate lines like:
    'Nov 14,\n2025' → 'Nov 14, 2025'
    """
    # Join month-day-comma newline year
    text = re.sub(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s*\n\s*(\d{4})",
        lambda m: f"{m.group(1)} {m.group(2)}", 
        text,
        flags=re.IGNORECASE
    )

    # Also join if it's split by <br> or multiple spaces
    text = text.replace("<br>", " ").replace("\r\n", " ").replace("\n", " ")

    return text



# =============================
# Utility Functions
# =============================

def extract_text_and_html(html):
    try:
        soup = BeautifulSoup(html, "html.parser")
        full_html = soup.prettify().lower()
        text = soup.get_text(separator=" ", strip=True).lower()
        return full_html, text
    except:
        return html.lower(), html.lower()


def detect_brand(text, html, sender, subject):

    # 1. Try weighted JSON brand detection
    json_brand, json_category = weighted_brand_match(text, sender, subject)

    # RULE: If a merchant (non-gateway) matches, and a payment gateway also matches,
    # keep the merchant and ignore the gateway.
    GATEWAYS = {"razorpay", "stripe", "cashfree", "ccavenue", "payu", "paypal", "google_play"}

    if json_brand in GATEWAYS:
        # check if any merchant appears in text explicitly
        for merchant in BRANDS.keys():
            if merchant not in GATEWAYS:
                merchant_patterns = BRANDS[merchant].get("patterns", [])
                for p in merchant_patterns:
                    if re.search(p, text, flags=re.IGNORECASE):
                        # merchant found! override gateway
                        return merchant, BRANDS[merchant]["category"], 0.98

    # Otherwise accept JSON brand match
    if json_brand:
        return json_brand, json_category, 0.95


    # 2. Fallback to sender-domain inference
    sender_brand = extract_brand_from_sender(sender)
    if sender_brand:
        return sender_brand, "others", 0.75

    # 3. Fallback to capitalized brand name extraction (subject/body)
    inferred_brand = extract_brand_from_text(subject + " " + text)
    if inferred_brand:
        return inferred_brand, "others", 0.6

    # 4. Fallback to HTML <img alt=""> logo detection
    html_brand = extract_brand_from_html(html)
    if html_brand:
        return html_brand, "others", 0.7

    # 5. Nothing found
    return None, "others", 0.0



def extract_amount(text, html, subject):
    """
    High-accuracy amount extractor with:
    - HTML digit normalization
    - strict validation
    - contextual scoring
    """

    subject_lower = subject.lower()
    text_lower = text.lower()

    normalized_html = normalize_html_amounts(html)
    candidates = []

    # Unified regex patterns for amounts
    AMOUNT_PATTERNS = [
        # INR / Rs / ₹ patterns
        r"(?:rs\.?|inr|₹)\s*([0-9]{1,3}(?:[, ]?\d{2,3})*(?:\.\d{1,2})?)",
        r"([0-9]{1,3}(?:[, ]?\d{2,3})*(?:\.\d{1,2})?)\s*(?:rs\.?|inr|₹)",

        # USD patterns
        r"(?:usd|us\$|\$)\s*([0-9]{1,3}(?:[, ]?\d{2,3})*(?:\.\d{1,2})?)",
        r"([0-9]{1,3}(?:[, ]?\d{2,3})*(?:\.\d{1,2})?)\s*(?:usd|us\$|\$)",

        # Generic "Total", "Amount", etc.
        r"\btotal[: ]*([0-9]{1,3}(?:[, ]?\d{2,3})*(?:\.\d{1,2})?)\b",
        r"\bamount(?: paid| due| charged)?[: ]*([0-9]{1,3}(?:[, ]?\d{2,3})*(?:\.\d{1,2})?)"
    ]


    # -----------------------------------------------------
    # 1. Match in normalized HTML (most reliable)
    # -----------------------------------------------------
    for pattern in AMOUNT_PATTERNS:
        for match in re.findall(pattern, normalized_html, flags=re.IGNORECASE):
            amt = (
                match.lower()
                .replace(",", "")
                .replace("$", "")
                .replace("us$", "")
                .replace("usd", "")
                .strip()
            )

            if amt.replace(".", "", 1).isdigit() and is_valid_amount(amt):
                candidates.append(("html", float(amt)))

    # -----------------------------------------------------
    # 2. Fallback: Match in plain body text
    # -----------------------------------------------------
    for pattern in AMOUNT_PATTERNS:
        for match in re.findall(pattern, text_lower, flags=re.IGNORECASE):
            amt = (
                match.lower()
                .replace(",", "")
                .replace("$", "")
                .replace("us$", "")
                .replace("usd", "")
                .strip()
            )

            if amt.replace(".", "", 1).isdigit() and is_valid_amount(amt):
                candidates.append(("text", float(amt)))

    # -----------------------------------------------------
    # No valid amount found
    # -----------------------------------------------------
    if not candidates:
        return None, 0.0

    # -----------------------------------------------------
    # 3. Score candidates
    # -----------------------------------------------------
    scored = []
    for source, amt in candidates:
        score = 0.4 if source == "html" else 0.3   # HTML is usually more trustworthy

        # Receipt context in subject
        if any(k in subject_lower for k in ["invoice", "receipt", "order", "payment"]):
            score += 0.3

        # Financial keywords near content
        for w in ["total", "amount", "paid", "charged", "transaction"]:
            if w in text_lower:
                score += 0.2
                break

        # Discount / % case → penalty
        if f"{amt}%" in text_lower:
            score -= 0.5

        scored.append((amt, score))

    # -----------------------------------------------------
    # 4. Choose best-scoring amount
    # -----------------------------------------------------
    best_amount, best_score = max(scored, key=lambda x: x[1])

    # -----------------------------------------------------
    # 5. If final score weak → reject
    # -----------------------------------------------------
    if best_score < 0.45:
        return None, 0.0

    return str(best_amount), round(min(best_score, 1.0), 3)




def extract_date(text, html, meta_date, subject):
    clean_html = normalize_broken_dates(html)
    clean_text = normalize_broken_dates(text)

    match = DATE_REGEX.search(clean_html)
    if match:
        extracted = match.group(0)
        confidence = 0.6
        if any(k in subject for k in RECEIPT_META):
            confidence += 0.2
        return extracted, min(confidence, 1.0)

    # fallback to text
    match = DATE_REGEX.search(clean_text)
    if match:
        extracted = match.group(0)
        return extracted, 0.6

    # fallback to metadata
    if any(k in subject for k in RECEIPT_META):
        return meta_date, 0.5

    return None, 0.0



def extract_frequency(text):
    text = text.lower()

    # 1. Direct regex match
    for freq, patterns in FREQ_PATTERNS.items():
        for p in patterns:
            if re.search(p, text):
                return freq, 0.9

    # 2. Check pricing shorthand like ₹199/month or $9.99/yr
    if re.search(r"/\s*(mo|mon|month)", text):
        return "monthly", 0.85
    if re.search(r"/\s*(yr|year)", text):
        return "yearly", 0.85
    if re.search(r"/\s*wk", text):
        return "weekly", 0.85

    # 3. Deduce from "renews on" + pattern like "every month"
    if "renews on" in text and "month" in text:
        return "monthly", 0.7
    if "renews on" in text and "year" in text:
        return "yearly", 0.7

    # 4. Deduce from date interval (most advanced)
    # e.g. next billing date → +30 days → monthly
    date_matches = re.findall(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b", text)
    if len(date_matches) >= 2:
        try:
            from datetime import datetime
            d1 = datetime.strptime(date_matches[0], "%d/%m/%Y")
            d2 = datetime.strptime(date_matches[1], "%d/%m/%Y")
            diff = abs((d2 - d1).days)
            if 27 <= diff <= 33:
                return "monthly", 0.75
            if 350 <= diff <= 380:
                return "yearly", 0.75
            if 6 <= diff <= 8:
                return "weekly", 0.75
        except:
            pass  # ignore errors

    # 5. Nothing detected
    return None, 0.0


def is_receipt(text, html, subject):
    text_lower = text.lower()
    subject_lower = subject.lower()

    score = 0

    # --------------------------------------------
    # Signal 1: Amount detection using improved extractor
    # --------------------------------------------
    extracted_amount, amt_conf = extract_amount(text, html, subject)
    if extracted_amount is not None and amt_conf >= 0.4:
        score += 2     # amount = strongest receipt signal

    # --------------------------------------------
    # Signal 2: Date detection
    # --------------------------------------------
    if DATE_REGEX.search(html) or DATE_REGEX.search(text_lower):
        score += 1

    # --------------------------------------------
    # Signal 3: Order/transaction ID
    # --------------------------------------------
    if ID_REGEX.search(text_lower):
        score += 1

    # --------------------------------------------
    # Signal 4: Subject keywords
    # --------------------------------------------
    receipt_keywords = [
    "invoice", "payment", "receipt", "order", "transaction", 
    "confirmed", "thank you", "you've made a purchase", "purchase"
    ]

    if any(k in subject_lower for k in receipt_keywords):
        score += 1

    # --------------------------------------------
    # Signal 5: Body keywords (context confirmation)
    # --------------------------------------------
    body_keywords = ["payment", "transaction", "order", "billed", "charged", "thank", "purchase", "purchased"]

    if any(k in text_lower for k in body_keywords):
        score += 1

    # --------------------------------------------
    # Avoid counting promo emails as receipts
    # --------------------------------------------
    promo_words = ["offer", "save", "discount", "sale", "cashback"]
    if any(w in subject_lower for w in promo_words):
        score -= 1
    if any(w in text_lower for w in promo_words):
        score -= 1

    # --------------------------------------------
    # FINAL DECISION RULE
    # --------------------------------------------

    # Score Interpretation:
    # 0–1 → definitely not a receipt
    # 2   → suspicious / weak → NOT counted
    # 3+  → valid receipt (multiple confirmations)

    return score >= 3



def classify_type(text, html, subject):
    text_lower = text.lower()

    # If subscription words appear, force subscription type
    if any(k in text_lower for k in RECURRING_KEYWORDS):
        return "subscription"

    # Otherwise do normal receipt validation
    if not is_receipt(text, html, subject):
        return "others"

    # Default receipt type → purchase
    return "purchase"


def receipt_negation_confidence(text, html, subject):
    """
    Returns confidence that the email is NOT a receipt.
    """
    score = 0

    subject = subject.lower()
    text = text.lower()

    # If subject lacks any receipt words → higher confidence it's NOT a receipt
    if not any(k in subject for k in RECEIPT_META):
        score += 0.4

    # If no amount found at all → strong indicator it's NOT a receipt
    amt, amt_conf = extract_amount(text, html, subject)
    if amt is None:
        score += 0.4

    # If no transaction/order ID → more non-receipt-like
    if not ID_REGEX.search(text):
        score += 0.2

    return round(min(score, 1.0), 3)




# =============================
# Main Processor
# =============================

def process_mails():
    with open("output.json", "r", encoding="utf-8") as f:
        mails = json.load(f)

    output = []

    for mail in mails:

        sender = mail["metadata"].get("from", "").lower()
        subject = mail["metadata"].get("subject", "").lower()
        meta_date = mail["metadata"].get("date", "")

        html, text = extract_text_and_html(mail.get("body", ""))


        raw_html = mail["body"]
        sender = mail["metadata"].get("from", "").lower()
        subject = mail["metadata"].get("subject", "").lower()

        brand, category, brand_confidence = detect_brand(text, raw_html, sender, subject)


        mail_type = classify_type(text, html, subject)

        mail["brand"] = brand
        mail["category"] = category
        mail["type"] = mail_type

        # Default
        mail["overall_confidence"] = 0.0

        if mail_type == "others":
            mail["overall_confidence"] = receipt_negation_confidence(text, html, subject)
            output.append(mail)
            continue

        # === Extract structured fields ===
        amount, amount_conf = extract_amount(text, html, subject)
        date, date_conf = extract_date(text, html, meta_date, subject)

        mail["amount"] = amount
        mail["amount_confidence"] = amount_conf

        if mail_type == "purchase":
            mail["date"] = date
            mail["date_confidence"] = date_conf

        elif mail_type == "subscription":
            freq, freq_conf = extract_frequency(text)
            mail["start_date"] = date
            mail["start_date_confidence"] = date_conf
            mail["frequency"] = freq
            mail["frequency_confidence"] = freq_conf

        # === Overall confidence ===
        conf_values = [amount_conf, date_conf]
        mail["overall_confidence"] = round(sum(conf_values) / len(conf_values), 3)

        output.append(mail)

    with open("categorized_mails.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print("✔ HIGH ACCURACY categorized_mails.json generated!")

    return output


if __name__ == "__main__":
    process_mails()



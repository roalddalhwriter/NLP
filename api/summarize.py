from flask import Flask, request, jsonify
import requests
import re
import os
import json
import google.generativeai as genai

app = Flask(__name__)

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# -------------------------------
# Extract YouTube Video ID
# -------------------------------
def extract_video_id(url):
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# -------------------------------
# Get Transcript
# -------------------------------
def get_transcript(video_id):
    url = f"https://api.supadata.ai/v1/youtube/transcript?videoId={video_id}&text=true"
    
    res = requests.get(
        url,
        headers={"x-api-key": os.environ.get("SUPADATA_API_KEY")}
    )

    if res.status_code != 200:
        raise Exception("Could not fetch transcript.")

    data = res.json()
    return data.get("content", "")

# -------------------------------
# Gemini Summarizer (SAFE)
# -------------------------------
def summarize_with_gemini(transcript):
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
You are an academic assistant.

Return ONLY valid JSON. No explanation, no markdown.

Format:
{{
  "summary": ["point 1", "point 2", "point 3", "point 4", "point 5", "point 6"],
  "viva": [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ]
}}

Transcript:
{transcript[:12000]}
"""

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0}
    )

    raw = response.text.strip()

    # Clean markdown if exists
    raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        return json.loads(raw)
    except Exception:
        print("❌ RAW GEMINI OUTPUT:\n", raw)
        raise Exception("Invalid JSON returned by model")

# -------------------------------
# API Route
# -------------------------------
@app.route("/api/summarize", methods=["POST"])
def summarize():
    try:
        data = request.get_json()
        url = data.get("url", "").strip()

        if not url:
            return jsonify({"error": "No URL provided"}), 400

        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL"}), 400

        transcript = get_transcript(video_id)
        if not transcript:
            return jsonify({"error": "Transcript not available"}), 400

        result = summarize_with_gemini(transcript)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Required for Vercel
handler = app

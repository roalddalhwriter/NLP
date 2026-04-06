from flask import Flask, request, jsonify
import requests
import re
import os
import google.generativeai as genai
import json

app = Flask(__name__)

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

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

def get_transcript(video_id):
    url = f"https://api.supadata.ai/v1/youtube/transcript?videoId={video_id}&text=true"
    res = requests.get(url, headers={"x-api-key": os.environ.get("SUPADATA_API_KEY")})
    
    if res.status_code != 200:
        raise Exception("Could not fetch transcript. Make sure the video has captions.")
    
    data = res.json()
    return data.get("content", "")

# ✅ NEW FUNCTION (Gemini)
def summarize_with_gemini(transcript):
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""You are an academic assistant. Given the following lecture transcript, produce:
1. A concise summary as 6-8 bullet points covering the key concepts.
2. Exactly 5 viva (oral exam) questions with thorough answers based on the content.

Respond ONLY with valid JSON in this exact format, no extra text:
{{
  "summary": ["bullet 1", "bullet 2", "bullet 3", ...],
  "viva": [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ]
}}

Transcript:
{transcript[:12000]}"""

    response = model.generate_content(prompt)

    raw = response.text.strip()

    # Clean markdown if Gemini adds it
    raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE).strip()

    return json.loads(raw)

@app.route("/api/summarize", methods=["POST"])
def summarize():
    try:
        data = request.get_json()
        url = data.get("url", "").strip()

        if not url:
            return jsonify({"error": "No URL provided."}), 400

        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL."}), 400

        transcript = get_transcript(video_id)
        if not transcript:
            return jsonify({"error": "Could not fetch transcript. Make sure the video has captions enabled."}), 400

        result = summarize_with_gemini(transcript)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app

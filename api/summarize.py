from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
import anthropic
import re
import os

app = Flask(__name__)

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
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    return " ".join([entry["text"] for entry in transcript_list])

def summarize_with_claude(transcript):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE).strip()
    import json
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

        result = summarize_with_claude(transcript)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app

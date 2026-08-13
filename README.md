# Indian History Reel Studio — FREE Mode

A zero-OpenAI-cost starter for the Master Indian History Reel workflow.

## Important trade-off

This version does **not** use the OpenAI API and does not require an API key. It uses public Wikipedia/Wikimedia API retrieval, AI Horde for community-powered free text/image generation, and optional `edge-tts` for Telugu narration. Free services can be queued, rate-limited, or change availability. Research quality is therefore not equivalent to a paid multi-source research stack.

For stricter historical fact-checking, paste source URLs or source notes into the app's source/evidence box and review the generated research report before publishing.

AI image consistency is enforced through a project Visual Bible and continuity prompts, but no free image service can guarantee pixel-perfect recurring faces across independent generations.

## Run

Python 3.11+ recommended.

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

No API key is required.

## Deploy

This can be deployed to Streamlit Community Cloud. Because this free version has no secret key, you can keep deployment simple. Be aware that public cloud environments may have storage/session limits, and AI Horde jobs may be slow.

## Output

Each project contains:
- research.json
- story.json
- visual_bible.json
- scenes.json
- voiceover_telugu.txt
- subtitles.srt
- editing_timeline.csv
- images/IMAGE_01.png ...
- audio/voiceover_te-IN-ShrutiNeural.mp3 when TTS succeeds

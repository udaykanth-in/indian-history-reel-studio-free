# Indian History Reel Studio — FREE v2

This version keeps the no-payment workflow and updates the text-generation layer to the current AI Horde OpenAI-compatible proxy. The proxy documents anonymous access with key `0000000000` at lowest priority. AI Horde is volunteer-powered and free to use, though anonymous jobs can be slower or restricted under load.

It also uses the current AI Horde REST base for image generation, public Wikipedia/Wikimedia retrieval with retries, and optional Telugu TTS through `edge-tts`.

## Deploy
Upload `app.py`, `requirements.txt`, and this README to the GitHub repository, then let Streamlit Cloud redeploy.

## No OpenAI API key is required.

## Privacy
Do not put private/sensitive material into AI Horde prompts; AI Horde documentation notes that worker operators may technically be able to see prompts/generations. Treat requests as public-forum-like.


### v3 reliability changes
- Requests a JSON response from the free AI Horde OpenAI-compatible proxy.
- Raises the text token ceiling to reduce truncated JSON.
- Uses balanced-brace JSON extraction as a fallback.

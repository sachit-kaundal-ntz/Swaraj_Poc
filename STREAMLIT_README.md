Streamlit UI for Technical Drawing Extraction

Files added
- `streamlit_app.py` — Streamlit front-end to upload an image, run extraction, and download outputs.

Add keys in folder 

```bash
.streamlit/secrets.toml
```

Requirements
- Python 3.8+ (project uses 3.12 in the venv here)
- Install Streamlit and other project dependencies from `requirements.txt` or the virtual environment in `env/`.

Run locally
1. Activate your virtual environment (if present):

```bash
source env/bin/activate
```

2. Install streamlit if not installed:

```bash
pip install streamlit
```

3. Run the Streamlit app:

```bash
streamlit run streamlit_app.py
```

Notes
- The extraction service calls Google's Gemini API. Ensure `GOOGLE_API_KEY` is set in your environment before running.

Security & leaked-key remediation
- If you previously committed a Google API key to this repository, treat it as leaked and rotate it immediately in the Google Cloud Console:
	1) Go to the Credentials page in your Google Cloud project and delete or disable the exposed API key.
 2) Create a new API key and apply restrictions (HTTP referrers, IP addresses, and enabled APIs) to limit misuse.
 3) Set the new key as an environment variable locally (recommended) e.g. `export GOOGLE_API_KEY="YOUR_NEW_KEY"` or use a local `.env` file that is in `.gitignore`.
 4) Never commit real API keys to source control. Use secret managers or environment variables for production deployments.
- This app currently supports basic raster images (png/jpg/tiff). If you need PDF support, convert pages to images first.

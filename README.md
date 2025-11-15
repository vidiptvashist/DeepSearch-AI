# DeepSearch-AI

DeepSearch-AI is a small Python-based prototype that wires a minimal web frontend to a backend client for running semantic/deep search queries using a generative model client (the repository contains a Gemini client wrapper). It's intended as a lightweight starting point for experimenting with search and LLM-powered retrieval.

## Features

- Minimal Python backend (in `app/`) that integrates with a language-model client.
- Static single-page frontend located in `static/index.html` for sending queries and viewing results.
- Simple dependency wiring in `app/deps.py` and a dedicated `gemini_client.py` for model API calls.

## Repository layout

```
LICENSE
README.md                # (this file)
requirements.txt         # Python dependencies
app/
	deps.py              # dependency setup / wiring
	gemini_client.py     # client wrapper for the Gemini model API
	main.py              # small server / runner
static/
	index.html           # frontend UI
```

## Prerequisites

- Python 3.10+ (recommended). Adjust if your environment uses a different minor version.
- A virtual environment (recommended) and the required Python packages listed in `requirements.txt`.
- An API key / credentials for the back-end model provider. The project includes a `gemini_client.py` file which expects credentials to be provided via environment variables (see assumptions below).


## Install

1. Create and activate a virtualenv (macOS / zsh):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your API key (example):

```bash
GEMINI_API_KEY = 
SUPABASE_URL = 
SUPABASE_SERVICE_ROLE_KEY =  
SUPABASE_ANON_KEY = 
SUPABASE_JWT_SECRET = 


```

## Run the app

From the project root you can run the backend directly. The repository includes a minimal `app/main.py` entrypoint; run it like:

```bash
python app/main.py
```

Then open `static/index.html` in your browser or point the front-end to the backend endpoint (if `main.py` serves the static files or exposes an API). If `main.py` launches a web server, the console output will show the URL and port.

If you prefer to run via a module path (depending on how `main.py` is implemented):

```bash
python -m app.main
```

## Development notes

- `app/deps.py` contains dependency wiring. Use it to centralize configuration for clients and other components.
- `app/gemini_client.py` wraps the language model API. If you change providers, update or replace this module.
- Keep credentials out of source control. Use environment variables or a secrets manager.

## Testing

This repository currently does not include automated tests. Suggested next steps:

- Add unit tests for `gemini_client.py` to mock API calls.
- Add an integration test that spins up `app/main.py` and exercises the HTTP endpoints.

## Contributing

Contributions are welcome. Typical workflow:

1. Fork the repo.
2. Create a feature branch.
3. Add or update tests for new behavior.
4. Open a pull request describing your changes.


## Contact

If you have questions, open an issue in this repository describing the problem or feature request.

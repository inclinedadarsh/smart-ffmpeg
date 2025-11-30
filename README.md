# Smart FFmpeg

A CLI tool that uses OpenRouter (LLM) to translate natural language into FFmpeg commands and execute them.

## Setup

1.  **Install `uv`** (if not already installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Install Dependencies**:
    ```bash
    uv sync
    ```

3.  **Configuration**:
    Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
    
    Edit `.env` and add your API key:
    ```ini
    OPENROUTER_API_KEY=your_key_here
    OPENROUTER_MODEL=google/gemini-2.0-flash-001 # Optional: Change model if needed
    ```

## Usage

Run the tool using `uv`:

```bash
uv run smart_ffmpeg.py
```

Or if installed:

```bash
smart-ffmpeg
```

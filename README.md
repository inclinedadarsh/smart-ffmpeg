# Smart FFmpeg

A CLI tool that uses OpenRouter (LLM) to translate natural language into FFmpeg commands and execute them.

## Installation (Binary)

You can download the standalone binary for Linux and macOS from the [Releases page](https://github.com/inclinedadarsh/smart-ffmpeg/releases).

1.  Download the binary for your OS (`smart-ffmpeg-linux` or `smart-ffmpeg-macos`).
2.  Make it executable:
    ```bash
    chmod +x smart-ffmpeg-linux
    mv smart-ffmpeg-linux smart-ffmpeg
    ```
3.  Run it:
    ```bash
    ./smart-ffmpeg
    ```

## Development Setup

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

## Build & Install (Linux)

To create a standalone binary for Linux:

1.  **Build the binary**:
    ```bash
    make build
    ```
    The executable will be created at `dist/smart-ffmpeg`.

2.  **Install system-wide** (optional):
    ```bash
    make install
    ```
    This will install the binary to `/usr/local/bin/smart-ffmpeg`.

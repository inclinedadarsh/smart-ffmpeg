#!/usr/bin/env python3
import os
import sys
import subprocess
import shlex
import json
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.status import Status
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

console = Console()

def get_api_key() -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] OPENROUTER_API_KEY not found in environment variables.")
        console.print("Please set it in a .env file or export it in your shell.")
        sys.exit(1)
    return api_key

def get_ffmpeg_command(client: OpenAI, prompt: str, model: str = None) -> dict:
    """
    Generates an FFmpeg command from a natural language prompt using OpenRouter.
    Returns a dictionary with 'command' and 'explanation'.
    """
    if model is None:
        model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    
    system_prompt = """
You are an expert FFmpeg command generator. 
Your task is to translate the user's natural language request into a valid, efficient FFmpeg command.

You must output your response in valid JSON format with the following structure:
{
    "command": "the full ffmpeg command here",
    "explanation": "a brief explanation of what the command does"
}

- Ensure the command is safe and correct.
- Do not include markdown formatting (like ```json) around the output, just the raw JSON string.
- If the user's request is ambiguous, make a reasonable assumption and note it in the explanation.
- Assume standard input/output filenames if none are provided (e.g., input.mp4, output.mp4), or placeholders like <input_file>.
    """

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}, # Force JSON if supported, otherwise system prompt handles it
        )
        
        content = response.choices[0].message.content.strip()
        
        # cleanup markdown if the model adds it despite instructions
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        return json.loads(content.strip())
    except json.JSONDecodeError:
        console.print("[bold red]Error:[/bold red] Failed to parse model response as JSON.")
        console.print(f"Raw response: {content}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error generating command:[/bold red] {str(e)}")
        sys.exit(1)

def run_ffmpeg_command(command: str):
    """
    Executes the FFmpeg command and streams output.
    """
    console.print(f"\n[bold green]Running command...[/bold green]")
    
    try:
        # Split command for subprocess
        args = shlex.split(command)
        
        # Check if ffmpeg is installed
        if args[0] != 'ffmpeg':
             # In case the model didn't start with ffmpeg or user aliased it, 
             # but usually we expect 'ffmpeg'. Let's trust the model but verify binary exists.
             pass

        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # FFmpeg writes status to stderr
            text=True,
            bufsize=1
        )
        
        # Stream output
        with console.status("[bold green]Processing video...[/bold green]", spinner="dots"):
            for line in process.stdout:
                # We can print the raw output or try to parse progress.
                # For simplicity and "Rich" feel, let's print dimmed logs.
                console.print(line.strip(), style="dim", highlight=False)
        
        return_code = process.wait()
        
        if return_code == 0:
            console.print("\n[bold green]Success![/bold green] command executed successfully.")
        else:
            console.print(f"\n[bold red]Failed![/bold red] Command exited with code {return_code}.")
            
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] 'ffmpeg' command not found. Is FFmpeg installed?")
    except Exception as e:
        console.print(f"[bold red]Execution Error:[/bold red] {str(e)}")

def main():
    console.print(Panel.fit("[bold blue]Smart FFmpeg CLI[/bold blue] 🎬\n[italic]Powered by OpenRouter & Rich[/italic]"))
    
    api_key = get_api_key()
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Check for command line arguments (non-interactive mode)
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        process_request(client, prompt)
        return

    # Interactive mode
    while True:
        console.print("\n[bold yellow]What do you want to do?[/bold yellow] (or 'exit' to quit)")
        user_input = Prompt.ask(">>")
        
        if user_input.lower() in ('exit', 'quit', 'q'):
            console.print("[bold blue]Goodbye![/bold blue]")
            break
        
        if not user_input.strip():
            continue
            
        process_request(client, user_input)

def process_request(client: OpenAI, prompt: str):
    with console.status("[bold cyan]Generating command...[/bold cyan]", spinner="arc"):
        result = get_ffmpeg_command(client, prompt)
        
    command = result.get("command")
    explanation = result.get("explanation")
    
    console.print("\n[bold]Generated Command:[/bold]")
    console.print(Syntax(command, "bash", theme="monokai", word_wrap=True))
    console.print(Panel(explanation, title="Explanation", title_align="left", border_style="green"))
    
    if Confirm.ask("Do you want to run this command?", default=True):
        run_ffmpeg_command(command)

if __name__ == "__main__":
    main()

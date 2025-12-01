#!/usr/bin/env python3
import os
import sys
import subprocess
import shlex
import json
from typing import Optional, List, Dict
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.syntax import Syntax
from rich.status import Status
from dotenv import load_dotenv
from openai import OpenAI
import questionary
import tempfile

# Load environment variables
load_dotenv()

console = Console()

DEFAULT_SYSTEM_PROMPT = """
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
""".strip()

class Config:
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "smart-ffmpeg"
        self.config_file = self.config_dir / "config.json"
        self.ensure_config_dir()
        self.data = self.load_config()

    def ensure_config_dir(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> Dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {"always_allow": False}
        return {"always_allow": False, "custom_system_prompt": None}

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    @property
    def always_allow(self) -> bool:
        return self.data.get("always_allow", False)

    @always_allow.setter
    def always_allow(self, value: bool):
        self.data["always_allow"] = value
        self.save_config()

    @property
    def custom_system_prompt(self) -> Optional[str]:
        return self.data.get("custom_system_prompt")

    @custom_system_prompt.setter
    def custom_system_prompt(self, value: Optional[str]):
        self.data["custom_system_prompt"] = value
        self.save_config()

config = Config()

def get_api_key() -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] OPENROUTER_API_KEY not found in environment variables.")
        console.print("Please set it in a .env file or export it in your shell.")
        sys.exit(1)
    return api_key

def get_ffmpeg_command(client: OpenAI, messages: List[Dict], model: str = None) -> dict:
    """
    Generates an FFmpeg command from a conversation history using OpenRouter.
    Returns a dictionary with 'command' and 'explanation'.
    """
    if model is None:
        model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    
    if config.custom_system_prompt:
        system_prompt = config.custom_system_prompt
    else:
        system_prompt = DEFAULT_SYSTEM_PROMPT
    
    conversation = [{"role": "system", "content": system_prompt}] + messages

    try:
        response = client.chat.completions.create(
            model=model,
            messages=conversation,
            response_format={"type": "json_object"}, 
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
        if args and args[0] != 'ffmpeg':
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

def process_request(client: OpenAI, initial_prompt: str):
    messages = [{"role": "user", "content": initial_prompt}]
    
    while True:
        with console.status("[bold cyan]Generating command...[/bold cyan]", spinner="arc"):
            result = get_ffmpeg_command(client, messages)
            
        command = result.get("command")
        explanation = result.get("explanation")
        
        console.print("\n[bold]Generated Command:[/bold]")
        console.print(Syntax(command, "bash", theme="monokai", word_wrap=True))
        console.print(Panel(explanation, title="Explanation", title_align="left", border_style="green"))
        
        # Add assistant response to history for context if user wants changes
        messages.append({"role": "assistant", "content": json.dumps(result)})

        if config.always_allow:
            console.print("[dim]Running automatically due to 'Always Allow' preference. Use /mode to change.[/dim]")
            run_ffmpeg_command(command)
            break
        
        # Interactive Menu
        # Ensure we are in a terminal that supports this, or fallback?
        # Questionary handles this reasonably well.
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Allow (Run command)",
                "Always Allow (Save preference & Run)",
                "Make Changes (Refine command)",
                "Reject (Cancel)"
            ],
            use_indicator=True,
            style=questionary.Style([
                ('qmark', 'fg:#E91E63 bold'),       
                ('question', 'bold'),               
                ('answer', 'fg:#2196f3 bold'),      
                ('pointer', 'fg:#673ab7 bold'),     
                ('highlighted', 'fg:#673ab7 bold'), 
                ('selected', 'fg:#cc5454'),         
                ('separator', 'fg:#cc5454'),        
                ('instruction', ''),                
                ('text', ''),                       
                ('disabled', 'fg:#858585 italic')   
            ])
        ).ask()

        if choice == "Allow (Run command)":
            run_ffmpeg_command(command)
            break
        elif choice == "Always Allow (Save preference & Run)":
            config.always_allow = True
            console.print("[bold green]Preference saved![/bold green] Future commands will run automatically.")
            run_ffmpeg_command(command)
            break
        elif choice == "Make Changes (Refine command)":
            refinement = questionary.text("Describe the changes needed:").ask()
            if refinement:
                messages.append({"role": "user", "content": refinement})
                continue # Loop back to generate new command
            else:
                console.print("[yellow]No changes entered. Retaining previous command.[/yellow]")
                # Could just loop back with no change or break. Let's loop back.
                continue
        else: # Reject
            console.print("[red]Command rejected.[/red]")
            break

def main():
    banner = r"""
 [bold blue]_____                      _      ____________                          
/  ___|                    | |     |  ___|  ___|                         
\ `--. _ __ ___   __ _ _ __| |_    | |_  | |_ _ __ ___  _ __   ___  __ _ 
 `--. \ '_ ` _ \ / _` | '__| __|   |  _| |  _| '_ ` _ \| '_ \ / _ \/ _` |
/\__/ / | | | | | (_| | |  | |_    | |   | | | | | | | | |_) |  __/ (_| |
\____/|_| |_| |_|\__,_|_|   \__|   \_|   \_| |_| |_| |_| .__/ \___|\__, |
                                                       | |          __/ |
                                                       |_|         |___/ [/bold blue]
    """
    console.print(banner)
    console.print("[italic]AI-Powered FFmpeg Command Generator[/italic]\n")
    
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
        mode_str = "Always Allow" if config.always_allow else "Ask"
        console.print(f"\n[dim]Current Mode: {mode_str} (Use /mode to toggle)[/dim]")
        console.print("[bold yellow]What do you want to do?[/bold yellow] (or '/exit' to quit)")
        
        user_input = Prompt.ask(">>")
        
        if not user_input.strip():
            continue

        if user_input.strip().lower() == '/exit':
            console.print("[bold blue]Goodbye![/bold blue]")
            break
        
        if user_input.strip() == '/mode':
            config.always_allow = not config.always_allow
            new_mode = "Always Allow" if config.always_allow else "Ask"
            console.print(f"[bold green]Mode switched to: {new_mode}[/bold green]")
            continue
        
        if user_input.strip() == '/prompt':
            while True:
                prompt_choice = questionary.select(
                    "Custom System Prompt Management:",
                    choices=[
                        "View Current Prompt",
                        "Edit Prompt (Open Editor)",
                        "Reset to Default",
                        "Back"
                    ]
                ).ask()

                if prompt_choice == "View Current Prompt":
                    current_prompt = config.custom_system_prompt if config.custom_system_prompt else DEFAULT_SYSTEM_PROMPT
                    is_custom = "(Custom)" if config.custom_system_prompt else "(Default)"
                    console.print(f"\n[bold]Current System Prompt {is_custom}:[/bold]")
                    console.print(Panel(current_prompt, border_style="blue"))
                
                elif prompt_choice == "Edit Prompt (Open Editor)":
                    # Start with existing custom prompt or the default one
                    initial_content = config.custom_system_prompt if config.custom_system_prompt else DEFAULT_SYSTEM_PROMPT
                    
                    editor = os.environ.get('EDITOR', 'nano')
                    
                    with tempfile.NamedTemporaryFile(mode='w+', suffix=".txt", delete=False) as tf:
                        tf.write(initial_content)
                        tf_path = tf.name
                    
                    try:
                        console.print(f"[dim]Opening editor ({editor})...[/dim]")
                        cmd = editor.split() + [tf_path] if " " in editor else [editor, tf_path]
                        subprocess.call(cmd)
                        
                        with open(tf_path, 'r') as tf:
                            new_content = tf.read().strip()
                        
                        if new_content and new_content != initial_content:
                            config.custom_system_prompt = new_content
                            console.print("[bold green]System prompt updated![/bold green]")
                        elif not new_content:
                             console.print("[yellow]Prompt was empty. No changes saved.[/yellow]")
                        else:
                            console.print("[yellow]No changes made.[/yellow]")

                    except Exception as e:
                        console.print(f"[bold red]Error opening editor:[/bold red] {str(e)}")
                    finally:
                        if os.path.exists(tf_path):
                            os.remove(tf_path)
                            
                elif prompt_choice == "Reset to Default":
                    if config.custom_system_prompt:
                        if questionary.confirm("Are you sure you want to clear the custom prompt and revert to default?").ask():
                            config.custom_system_prompt = None
                            console.print("[bold green]Reverted to default system prompt.[/bold green]")
                    else:
                        console.print("[yellow]Already using default system prompt.[/yellow]")
                        
                elif prompt_choice == "Back":
                    break
            continue
            
        process_request(client, user_input)

if __name__ == "__main__":
    main()
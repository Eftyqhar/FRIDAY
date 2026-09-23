import sys
import os
import time
import argparse
import asyncio
import subprocess
import urllib.request
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from config import config, AgentConfig
from agent import AutonomousBrowserAgent

console = Console()

BANNER = """
[bold cyan]╔══════════════════════════════════════════════════════════════╗
║               🤖 F.R.I.D.A.Y. Browser Copilot                ║
║        Autonomous Web Assistant (Playwright & Brave)         ║
╚══════════════════════════════════════════════════════════════╝[/bold cyan]
"""


async def run_task(
    task: str,
    start_url: Optional[str] = None,
    headed: bool = False,
    max_steps: Optional[int] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    isolated_profile: bool = False
):
    """Executes a single task."""
    cfg = AgentConfig()
    if headed:
        cfg.headless = False
    if max_steps:
        cfg.max_steps = max_steps
    if model:
        cfg.model_name = model
    if base_url:
        cfg.base_url = base_url.rstrip("/")
    if isolated_profile:
        cfg.isolated_profile = True

    agent = AutonomousBrowserAgent(cfg)
    result = await agent.run(task=task, start_url=start_url)
    return result

async def interactive_mode(
    headed: bool = False,
    base_url: Optional[str] = None,
    isolated_profile: bool = False
):
    """Interactive loop where the user can enter consecutive instructions."""
    console.print(BANNER)
    console.print("[green]Entering Interactive Mode. Type 'exit' or 'quit' to finish.[/green]\n")

    cfg = AgentConfig()
    if headed:
        cfg.headless = False
    if base_url:
        cfg.base_url = base_url.rstrip("/")
    if isolated_profile:
        cfg.isolated_profile = True

    while True:
        try:
            task = Prompt.ask("[bold yellow]Enter task[/bold yellow]")
            if task.strip().lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            if not task.strip():
                continue

            start_url = Prompt.ask("[dim]Start URL (optional, press Enter to skip)[/dim]", default="")
            start_url = start_url.strip() if start_url.strip() else None

            agent = AutonomousBrowserAgent(cfg)
            await agent.run(task=task, start_url=start_url)
            console.print("\n" + "─" * 60 + "\n")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

def connect_brave_cdp(port: int = 9222):
    """
    Connects to your real Brave profile with remote debugging enabled.
    Closes background instances locking the profile and launches Brave with your real 'Work' profile.
    """
    cfg = AgentConfig()
    brave_exe = cfg.browser_executable
    if not brave_exe or not os.path.exists(brave_exe):
        console.print("[bold red]Brave browser executable not found![/bold red]")
        return

    # Check if port 9222 is already listening
    try:
        req = urllib.request.Request(f"http://localhost:{port}/json/version", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=0.8) as res:
            if res.status == 200:
                console.print(f"[bold green]✓ Port {port} is already active on your Brave browser![/bold green]")
                console.print("[cyan]The agent will automatically attach to this browser when you run tasks.[/cyan]")
                return
    except Exception:
        pass

    console.print("[yellow]Preparing your real Brave profile ('Work')...[/yellow]")
    # Terminate background brave instances holding the lock
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/IM", "brave.exe", "/F"], capture_output=True, check=False)
    else:
        subprocess.run(["pkill", "-f", "brave"], capture_output=True, check=False)

    time.sleep(1.2)

    # Launch Brave with debugging port on the user's real profile
    cmd = [
        brave_exe,
        f"--remote-debugging-port={port}",
        f"--profile-directory={cfg.profile_name}",
        "--restore-last-session"
    ]
    console.print(f"[bold green]Launching your real Brave profile with remote debugging on port {port}...[/bold green]")
    subprocess.Popen(cmd)

    # Wait for CDP to respond
    console.print("[dim]Waiting for browser to be ready...[/dim]")
    ready = False
    for _ in range(15):
        time.sleep(0.5)
        try:
            req = urllib.request.Request(f"http://localhost:{port}/json/version", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=0.8) as res:
                if res.status == 200:
                    ready = True
                    break
        except Exception:
            pass

    if ready:
        console.print(Panel(
            f"[bold green]✓ Brave is ready with your real profile ('{cfg.profile_name}')![/bold green]\n\n"
            f"All your logins, tabs, and saved passwords are live.\n"
            f"Now run any task, e.g.:\n"
            f"  [bold cyan]python main.py run \"Go to github.com and check notifications\"[/bold cyan]",
            title="🦁 Real Brave Profile Connected",
            border_style="green"
        ))
    else:
        console.print("[yellow]Brave launched. If it doesn't respond on port 9222, ensure no antivirus is blocking localhost.[/yellow]")

def main():
    parser = argparse.ArgumentParser(
        description="FRIDAY: Autonomous Browser Assistant powered by Gemini & Playwright.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run a natural language browser task")
    run_parser.add_argument("task", type=str, help="The instruction to execute")
    run_parser.add_argument("--url", type=str, default=None, help="Initial URL to navigate to")
    run_parser.add_argument("--headed", action="store_true", help="Launch a visible browser window (default is headless)")
    run_parser.add_argument("--steps", type=int, default=25, help="Maximum steps allowed (default: 25)")
    run_parser.add_argument("--model", type=str, default=None, help="Gemini model name (e.g. gemini-2.5-flash)")
    run_parser.add_argument("--base-url", type=str, default=None, help="Custom API endpoint (e.g. https://api.hcnsec.cn)")
    run_parser.add_argument("--new-profile", action="store_true", help="Use a clean isolated profile instead of your real profile")

    # Command: interactive
    inter_parser = subparsers.add_parser("interactive", help="Start an interactive session")
    inter_parser.add_argument("--headed", action="store_true", help="Launch visible browser")
    inter_parser.add_argument("--base-url", type=str, default=None, help="Custom API endpoint (e.g. https://api.hcnsec.cn)")
    inter_parser.add_argument("--new-profile", action="store_true", help="Use a clean isolated profile instead of your real profile")

    # Command: connect-brave
    connect_parser = subparsers.add_parser("connect-brave", help="Connect directly to your real Brave profile with logged-in accounts")
    connect_parser.add_argument("--port", type=int, default=9222, help="Remote debugging port (default: 9222)")

    # Command: launch-brave (alias for connect-brave)
    launch_parser = subparsers.add_parser("launch-brave", help="Alias for connect-brave")
    launch_parser.add_argument("--port", type=int, default=9222, help="Remote debugging port (default: 9222)")

    # Command: test-browser
    test_parser = subparsers.add_parser("test-browser", help="Verify Playwright browser and screenshot pipeline")

    args = parser.parse_args()

    if not args.command:
        console.print(BANNER)
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        console.print(BANNER)
        asyncio.run(run_task(
            task=args.task,
            start_url=args.url,
            headed=args.headed,
            max_steps=args.steps,
            model=args.model,
            base_url=args.base_url,
            isolated_profile=args.new_profile
        ))
    elif args.command == "interactive":
        asyncio.run(interactive_mode(
            headed=args.headed,
            base_url=args.base_url,
            isolated_profile=args.new_profile
        ))
    elif args.command in ("connect-brave", "launch-brave"):
        connect_brave_cdp(port=args.port)
    elif args.command == "test-browser":
        from tests.test_agent import run_smoke_test
        asyncio.run(run_smoke_test())

if __name__ == "__main__":
    main()

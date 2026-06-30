"""User-facing notifications: console logging + an audible/desktop alert.

Kept dependency-light: a terminal bell always works; a desktop notification is
attempted on a best-effort basis per platform and silently degrades.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from rich.console import Console

console = Console()


def log(message: str, style: str = "") -> None:
    console.print(message, style=style)


def info(message: str) -> None:
    console.print(f"[dim]·[/dim] {message}")


def warn(message: str) -> None:
    console.print(f"[yellow]![/yellow] {message}", style="yellow")


def success(message: str) -> None:
    console.print(f"[green]✓[/green] {message}", style="bold green")


def error(message: str) -> None:
    console.print(f"[red]✗[/red] {message}", style="bold red")


def bell(times: int = 3) -> None:
    """Ring the terminal bell a few times."""
    for _ in range(max(1, times)):
        sys.stdout.write("\a")
    sys.stdout.flush()


def alert(title: str, message: str) -> None:
    """Loud, attention-grabbing alert: bell + best-effort desktop notification."""
    bell(5)
    console.rule(f"[bold red]{title}")
    console.print(message, style="bold")
    _desktop_notification(title, message)


def _desktop_notification(title: str, message: str) -> None:
    """Best-effort native desktop notification; never raises."""
    try:
        if sys.platform == "darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        elif sys.platform.startswith("linux") and shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=False, timeout=5)
        elif sys.platform.startswith("win"):
            # Powershell toast is finicky; fall back to a message box.
            ps = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms')"
                f";[System.Windows.Forms.MessageBox]::Show('{message}','{title}')"
            )
            subprocess.run(["powershell", "-Command", ps], check=False, timeout=5)
    except Exception:
        pass

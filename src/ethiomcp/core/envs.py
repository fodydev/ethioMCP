"""Per-connector virtual environments.

The server never imports connector libraries. A connector that needs one gets
its own venv with the Python version it asks for, so it cannot conflict with
the server's Python version or with other connectors.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


def env_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _run(cmd: list[str], log: Callable[[str], None]) -> None:
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)


def create_env(
    venv: Path,
    python: str,
    requirements: list[str],
    *,
    force: bool = False,
    log: Callable[[str], None] = print,
) -> None:
    """Create ``venv`` with a Python matching ``python`` and install the requirements."""
    if force and venv.exists():
        shutil.rmtree(venv)
    venv.parent.mkdir(parents=True, exist_ok=True)
    uv = shutil.which("uv")

    if not env_python(venv).exists():
        if uv:
            # uv finds a matching interpreter, or downloads one.
            _run([uv, "venv", "--python", python, str(venv)], log)
        else:
            log(f"uv not found; creating the venv with {sys.executable} (needs {python})")
            _run([sys.executable, "-m", "venv", str(venv)], log)

    if requirements:
        if uv:
            _run([uv, "pip", "install", "--python", str(env_python(venv)), *requirements], log)
        else:
            _run([str(env_python(venv)), "-m", "pip", "install", *requirements], log)


def run_in_env(venv: Path, code: str, log: Callable[[str], None] = print) -> None:
    """Run a Python snippet inside the venv, with no stdin so it cannot prompt."""
    _run([str(env_python(venv)), "-c", code], log)

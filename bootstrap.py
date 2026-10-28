"""
bootstrap.py - gets this project ready to run. You do not need to edit this file.

main.py calls ensure_ready() on its first line. Every time you run main.py it:

  1. Checks that your Python is new enough.
  2. Makes sure your API key is saved on this computer. The first time, it asks
     you to paste the key, then remembers it for every project.
  3. Creates the .venv folder and installs requirements.txt. This happens on the
     first run, and again only if requirements.txt changes.
  4. Restarts main.py inside .venv, so all the installed packages are available.

The project runs from any folder you extract it to, for example your Desktop.
Nothing here depends on where the folder is.

Your API key is NOT stored in this project folder. It is saved in
    Windows: C:\\Users\\<you>\\.secrets\\api-keys.env
    Mac:     /Users/<you>/.secrets/api-keys.env
so it can never be uploaded to GitHub together with the project.

Extra options (type in the VS Code terminal):
    python main.py --reset-key     forget the saved key and ask for a new one
    python main.py --setup-only    set everything up, then stop without running
"""

import getpass
import hashlib
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path

MIN_PYTHON = (3, 10)
PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
STAMP = VENV_DIR / ".requirements-hash"
SECRETS_FILE = Path.home() / ".secrets" / "api-keys.env"
LINE = "=" * 64


def ensure_ready(keys=("NEXLLM_API_KEY",), key_help=None):
    """Prepare everything main.py needs. Call it before importing any package.

    keys      names of the API keys this project needs; use keys=() for none.
    key_help  optional text shown when asking for a key, e.g. where to get one.
    """
    _check_python()

    reset = _take_flag("--reset-key")
    setup_only = _take_flag("--setup-only")

    for name in keys:
        if reset:
            _forget_key(name)
        _ensure_key(name, key_help)

    _ensure_venv()

    if setup_only:
        print("Setup finished. Run main.py again (without --setup-only) to start the project.")
        sys.exit(0)

    if not _running_in_project_venv():
        _relaunch_inside_venv()


def require_inputs(files):
    """Stop with a clear message if input files the user must download are missing.

    files  dict mapping a path inside the project (e.g. "input/report.pdf")
           to where to get it (a web address or a short instruction).
    """
    missing = [(p, src) for p, src in files.items() if not (PROJECT_DIR / p).exists()]
    if not missing:
        return
    lines = ["Some input files are missing. Download them yourself and save them here:", ""]
    for path, source in missing:
        lines.append("  Save as: " + str(PROJECT_DIR / path))
        lines.append("  Get it from: " + source)
        lines.append("")
    lines.append("README.md, section 'Get the input files', has the details.")
    _stop("\n".join(lines))


# ---------------------------------------------------------------- checks

def _check_python():
    if sys.version_info < MIN_PYTHON:
        _stop(
            "This project needs Python %d.%d or newer, but this computer is using %s.\n"
            "Install a newer Python from https://www.python.org/downloads/ ,\n"
            "then restart VS Code and run main.py again."
            % (MIN_PYTHON[0], MIN_PYTHON[1], platform.python_version())
        )


# The project may live in any folder (Desktop, Documents, C:\dev ...). There is
# deliberately no check on the location. Instead, if setup fails, _setup_hints()
# explains the location-related causes that can actually break it.

def _long_paths_enabled():
    """True unless this is Windows with the 260-character path limit still on."""
    if os.name != "nt":
        return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
    except (OSError, ImportError):
        return False


def _setup_hints(error_text=""):
    """Plain-language causes worth checking after .venv creation or pip fails."""
    text = error_text.lower()
    hints = []
    if not _long_paths_enabled():
        hints.append(
            "If the messages mention 'Long Path', 'WinError 206' or 'No such file\n"
            "or directory': Windows on this computer limits file paths to 260\n"
            "characters, and some packages install files with very long names.\n"
            "This project folder's path is already %d characters long. Give the\n"
            "folder a shorter name, or extract the zip to a folder with a shorter\n"
            "path, then run main.py again." % len(str(PROJECT_DIR)))
    if os.name == "nt" or "denied" in text or "permission" in text:
        hints.append(
            "If the messages mention 'Access is denied', 'WinError 5' or\n"
            "'Permission': Windows Security may be blocking Python from writing\n"
            "here ('Controlled folder access' protects the Desktop and Documents).\n"
            "Allow Python there, or extract the project to a different folder.")
        hints.append(
            "If the messages mention 'WinError 32' or 'used by another process':\n"
            "close other VS Code windows or terminals running this project, then\n"
            "run main.py again.")
    hints.append("If it keeps failing, delete the .venv folder and run main.py again.")
    return "\n\n".join(hints)


# ---------------------------------------------------------------- API key

def _read_secrets():
    values = {}
    if SECRETS_FILE.exists():
        for raw in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_secrets(values):
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = "# API keys for your projects. Keep this file private; never upload it.\n"
    text += "".join("%s=%s\n" % (k, v) for k, v in values.items())
    SECRETS_FILE.write_text(text, encoding="utf-8")
    try:
        os.chmod(SECRETS_FILE, 0o600)  # only you can read it (Mac/Linux)
    except OSError:
        pass


def _forget_key(name):
    os.environ.pop(name, None)
    values = _read_secrets()
    if values.pop(name, None) is not None:
        _write_secrets(values)
        print("Forgot the saved " + name + ".")


def _ensure_key(name, key_help):
    if os.environ.get(name, "").strip():
        return
    value = _read_secrets().get(name, "")
    if not value:
        value = _ask_for_key(name, key_help)
        values = _read_secrets()
        values[name] = value
        _write_secrets(values)
        print("Saved. Your key is stored in " + str(SECRETS_FILE))
        print("That is outside this project, so it will never be uploaded to GitHub.\n")
    os.environ[name] = value


def _ask_for_key(name, key_help):
    print("\n" + LINE)
    print("This project needs your " + name + ".")
    if key_help:
        print(key_help)
    print("You only do this once on this computer.\n")
    print("Paste the key below and press Enter.")
    print("For your privacy nothing appears on screen while you paste. That is normal.")
    print(LINE)
    for _ in range(3):
        try:
            value = getpass.getpass(name + ": ").strip().strip('"').strip("'")
        except (EOFError, KeyboardInterrupt):
            value = ""
            break
        if value and " " not in value:
            print("Received a key ending in ...%s (%d characters)." % (value[-4:], len(value)))
            return value
        print("That did not look like a key. Please paste it again.")
    _stop(
        "No key was entered.\n"
        "Run main.py again and paste your key when asked, or add this line\n"
        "    " + name + "=your-key\n"
        "to the file " + str(SECRETS_FILE)
    )


# ---------------------------------------------------------------- .venv

def _venv_python():
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _running_in_project_venv():
    try:
        return Path(sys.prefix).resolve() == VENV_DIR.resolve()
    except OSError:
        return False


def _venv_works(py):
    try:
        return subprocess.run([str(py), "-c", "import sys"], capture_output=True).returncode == 0
    except OSError:
        return False


def _requirements_hash():
    data = REQUIREMENTS.read_bytes() if REQUIREMENTS.exists() else b""
    return hashlib.sha256(data).hexdigest()


def _ensure_venv():
    py = _venv_python()
    inside = _running_in_project_venv()
    if not inside and (not py.exists() or not _venv_works(py)):
        print("\nFirst run on this computer: creating the project environment (.venv) ...")
        try:
            venv.create(str(VENV_DIR), with_pip=True, clear=VENV_DIR.exists())
        except Exception as error:  # noqa: BLE001 - show any failure plainly
            _stop("Could not create the .venv folder:\n    %s\n\n%s"
                  % (error, _setup_hints(str(error))))
    if inside:
        py = Path(sys.executable)

    wanted = _requirements_hash()
    current = STAMP.read_text().strip() if STAMP.exists() else ""
    if wanted == current:
        return
    if REQUIREMENTS.exists() and REQUIREMENTS.read_text(encoding="utf-8").strip():
        print("\nInstalling the packages this project needs.")
        print("The first time this takes a few minutes. Please wait ...\n")
        result = subprocess.run([str(py), "-m", "pip", "install",
                                 "--disable-pip-version-check", "-r", str(REQUIREMENTS)])
        if result.returncode != 0:
            _stop("Installing packages failed. The messages above show which package.\n\n"
                  "Most often the internet connection dropped. Check it and run main.py\n"
                  "again; it continues where it stopped.\n\n" + _setup_hints())
    STAMP.write_text(wanted)
    print("\nSetup complete.\n")


def _relaunch_inside_venv():
    import __main__
    script = getattr(__main__, "__file__", None) or sys.argv[0]
    command = [str(_venv_python()), str(Path(script).resolve())] + sys.argv[1:]
    os.environ["BOOTSTRAP_CHILD"] = "1"  # marks the restarted copy of main.py
    try:
        code = subprocess.call(command, cwd=str(PROJECT_DIR))
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)


def _take_flag(flag):
    if flag in sys.argv:
        sys.argv.remove(flag)
        return True
    return False


def _stop(message):
    print("\n" + LINE)
    print(message)
    print(LINE + "\n")
    sys.exit(1)

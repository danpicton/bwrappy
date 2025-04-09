from pathlib import Path
import sys
import subprocess
from .runner import BwrapRunner

def main() -> None:
    """Entry point for the bwrappy package."""
    if len(sys.argv) < 3:
        print("Usage: bwrappy CONFIG_PATH COMMAND [ARGS...]", file=sys.stderr)
        sys.exit(1)
    
    config_path = Path(sys.argv[1])
    command = sys.argv[2:]
    
    try:
        runner = BwrapRunner(config_path, command, verbose=False)
        runner.execute()
    except subprocess.CalledProcessError as e:
        print(f"Sandbox failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


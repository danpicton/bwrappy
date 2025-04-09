import click
import subprocess
import sys
from pathlib import Path
from src.runner import BwrapRunner
from pydantic import ValidationError

@click.command()
@click.argument('config_path', type=click.Path(exists=True))
@click.argument('command', nargs=-1, required=True)
@click.option('-v', '--verbose', is_flag=True, help="Output the generated command.")
def run_sandbox(config_path, command, verbose):
    """Run a sandboxed command with bubblewrap using the provided YAML configuration."""
    try:
        runner = BwrapRunner(Path(config_path), list(command), verbose)
        runner.execute()
    except subprocess.CalledProcessError as e:
        click.echo(f"Sandbox failed with exit code {e.returncode}", err=True)
        sys.exit(e.returncode)
    except ValidationError as e:
        click.echo(f"Invalid config: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    run_sandbox()


import click
import subprocess
import sys
from pathlib import Path
from src.runner import BwrapRunner
from pydantic import ValidationError

@click.command(context_settings={
    "help_option_names": ["-h", "--help"],
    "ignore_unknown_options": True,
    "allow_interspersed_args": False  # This enforces options before arguments
})
@click.option('-c', '--config', 'config_paths', type=click.Path(exists=True), multiple=True, required=True,
              help="YAML configuration file(s). Can be specified multiple times.")
@click.option('-v', '--verbose', is_flag=True, help="Output the generated command.")
@click.argument('command', nargs=-1, required=True)
def run_sandbox(config_paths, command, verbose):
    """Run a sandboxed command with bubblewrap using the provided YAML configuration(s).
    
    All options must be specified before the command to run.
    
    Example: main.py -c base.yaml -c specific.yaml -v -- echo "hello world"
    """
    try:
        runner = BwrapRunner([Path(path) for path in config_paths], list(command), verbose)
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


import click
from pathlib import Path
from src.runner import BwrapRunner

@click.command()
@click.argument('config_path', type=click.Path(exists=True))
def run_sandbox(config_path):
    """Run the sandbox with the provided YAML configuration."""
    runner = BwrapRunner(Path(config_path))
    try:
        runner.execute()
    except subprocess.CalledProcessError as e:
        click.echo(f"Sandbox failed with exit code {e.returncode}")
    except ValidationError as e:
        click.echo(f"Invalid config: {e.errors()}")

if __name__ == "__main__":
    run_sandbox()


import pytest
import tempfile
import yaml
import sys
import subprocess
import os
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from main import run_sandbox

class TestMain:
    @pytest.fixture
    def cli_runner(self):
        return CliRunner()
        
    @pytest.fixture
    def temp_config_file(self):
        with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w') as f:
            config = {
                "namespaces": {
                    "share": ["net"]
                },
                "mounts": {
                    "binds": [
                        {"type": "ro", "src": "/etc/passwd", "dest": "/etc/passwd"}
                    ],
                    "tmpfs": ["/tmp"]
                }
            }
            yaml.dump(config, f)
            f.flush()
            yield f.name
            
    @patch("src.runner.BwrapRunner.execute")
    def test_run_sandbox_success(self, mock_execute, cli_runner, temp_config_file):
        mock_execute.return_value = MagicMock(returncode=0)
        
        result = cli_runner.invoke(
            run_sandbox, 
            [temp_config_file, "echo", "hello"],
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        mock_execute.assert_called_once()
    @patch("main.BwrapRunner")
    def test_run_sandbox_with_verbose(self, mock_runner_class, cli_runner, temp_config_file):
        # Create a mock instance that will be returned by the BwrapRunner constructor
        mock_runner_instance = MagicMock()
        mock_runner_instance.execute.return_value = MagicMock(returncode=0)
        mock_runner_class.return_value = mock_runner_instance
        
        result = cli_runner.invoke(
            run_sandbox,
            ["--verbose", temp_config_file, "echo", "hello"],
            catch_exceptions=False
        )
        
        assert result.exit_code == 0
        
        # Check that BwrapRunner was initialized with verbose=True
        args, kwargs = mock_runner_class.call_args
        
        # Check if verbose is passed as positional argument (it's the third parameter)
        if len(args) >= 3:
            assert args[2] is True, "verbose positional argument is not True"
        else:
            assert kwargs.get("verbose") is True, "verbose keyword argument is not True" 
        
    @patch("src.runner.BwrapRunner.execute", 
          side_effect=subprocess.CalledProcessError(1, ["bwrap"]))
    def test_run_sandbox_process_error(self, mock_execute, cli_runner, temp_config_file):
        result = cli_runner.invoke(
            run_sandbox, 
            [temp_config_file, "echo", "hello"]
        )
        
        assert result.exit_code == 1
        assert "Sandbox failed with exit code" in result.output
        
    def test_run_sandbox_nonexistent_config(self, cli_runner):
        result = cli_runner.invoke(
            run_sandbox, 
            ["/nonexistent/file.yaml", "echo", "hello"]
        )
        
        assert result.exit_code == 2  # Click's error code for file not found
        
    def test_run_sandbox_invalid_config(self, cli_runner, tmp_path):
        invalid_config = tmp_path / "invalid.yaml"
        invalid_config.write_text("invalid: : yaml")
        
        result = cli_runner.invoke(
            run_sandbox, 
            [str(invalid_config), "echo", "hello"]
        )
        
        assert result.exit_code == 1
        assert "Error:" in result.output

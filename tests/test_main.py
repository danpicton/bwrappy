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
            ["-c", temp_config_file, "echo", "hello"],
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
            ["-v", "-c", temp_config_file, "echo", "hello"],
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
            ["-c", temp_config_file, "echo", "hello"]
        )
        assert result.exit_code == 1
        assert "Sandbox failed with exit code" in result.output

    def test_run_sandbox_nonexistent_config(self, cli_runner):
        result = cli_runner.invoke(
            run_sandbox,
            ["-c", "/nonexistent/file.yaml", "echo", "hello"]
        )
        assert result.exit_code == 2  # Click's error code for file not found

    def test_run_sandbox_invalid_config(self, cli_runner, tmp_path):
        invalid_config = tmp_path / "invalid.yaml"
        invalid_config.write_text("invalid: : yaml")
        result = cli_runner.invoke(
            run_sandbox,
            ["-c", str(invalid_config), "echo", "hello"]
        )
        assert result.exit_code == 1
        assert "Error:" in result.output

    @patch("main.BwrapRunner")
    def test_run_sandbox_with_multiple_configs(self, mock_runner_class, cli_runner):
        # Create two temporary config files
        with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w') as f1, \
             tempfile.NamedTemporaryFile(suffix='.yaml', mode='w') as f2:
            
            # First config with basic settings
            config1 = {
                "namespaces": {
                    "share": ["net"]
                },
                "mounts": {
                    "binds": [
                        {"type": "ro", "src": "/etc/passwd", "dest": "/etc/passwd"}
                    ]
                }
            }
            yaml.dump(config1, f1)
            f1.flush()
            
            # Second config with additional settings
            config2 = {
                "mounts": {
                    "tmpfs": ["/tmp"]
                },
                "env": {
                    "set": {"TEST_VAR": "test_value"}
                }
            }
            yaml.dump(config2, f2)
            f2.flush()
            
            mock_runner_instance = MagicMock()
            mock_runner_instance.execute.return_value = MagicMock(returncode=0)
            mock_runner_class.return_value = mock_runner_instance
            
            result = cli_runner.invoke(
                run_sandbox,
                ["-c", f1.name, "-c", f2.name, "echo", "hello"],
                catch_exceptions=False
            )
            
            assert result.exit_code == 0
            mock_runner_class.assert_called_once()
            
            # Verify the BwrapRunner was initialized with both config files
            args, _ = mock_runner_class.call_args
            assert len(args[0]) == 2, "BwrapRunner should be called with 2 config files"
            assert str(args[0][0]) == f1.name, "First config file missing"
            assert str(args[0][1]) == f2.name, "Second config file missing"

    def test_cli_interface_multiple_configs(self, cli_runner):
        # Test showing the help
        result = cli_runner.invoke(run_sandbox, ["--help"])
        assert result.exit_code == 0
        
        # Verify our help text mentions the -c/--config option
        assert "-c, --config" in result.output
        assert "multiple" in result.output.lower()
    

import pytest
import os
import subprocess
from pathlib import Path
import tempfile
import yaml
from unittest.mock import patch, MagicMock
from src.runner import BwrapRunner, handle_fds

class TestRunner:
    @pytest.fixture
    def temp_config_file(self):
        with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w') as f:
            config = {
                "namespaces": {
                    "unshare": ["ipc", "pid"],
                    "share": ["net"]
                },
                "mounts": {
                    "binds": [
                        {"type": "ro", "src": "/etc/passwd", "dest": "/etc/passwd"},
                        {"dest": "/tmp/rw", "src": "/tmp"}
                    ],
                    "tmpfs": ["/tmp"]
                }
            }
            yaml.dump(config, f)
            f.flush()
            yield Path(f.name)
            
    def test_load_config(self, temp_config_file):
        runner = BwrapRunner(temp_config_file, ["echo", "hello"], False)
        assert runner.config.namespaces.unshare == ["ipc", "pid"]
        assert runner.config.namespaces.share == ["net"]
        assert len(runner.config.mounts["binds"]) == 2
        
    def test_load_config_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            BwrapRunner(Path("/nonexistent/file"), ["echo"], False)
            
    def test_load_config_invalid_yaml(self, tmp_path):
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("{invalid: yaml: content")
        with pytest.raises(ValueError):
            BwrapRunner(invalid_yaml, ["echo"], False)
            
    def test_build_args_basic(self, temp_config_file):
        runner = BwrapRunner(temp_config_file, ["echo", "hello"], False)
        args = runner._build_args()
        
        assert args[0] == "bwrap"
        assert "--unshare-ipc" in args
        assert "--unshare-pid" in args
        assert "--share-net" in args
        assert "--ro-bind" in args
        assert "/etc/passwd" in args
        assert "--bind" in args
        assert "/tmp" in args
        assert "--tmpfs" in args
        assert args[-2:] == ["echo", "hello"]
        
    @patch("subprocess.run")
    def test_execute(self, mock_run, temp_config_file):
        runner = BwrapRunner(temp_config_file, ["echo", "hello"], False)
        runner.execute()
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0][0] == "bwrap"
        assert "check" in kwargs and kwargs["check"] is True
        
    @patch("subprocess.run")
    def test_execute_with_verbose(self, mock_run, temp_config_file):
        runner = BwrapRunner(temp_config_file, ["echo", "hello"], True)
        with patch("builtins.print") as mock_print:
            runner.execute()
            mock_print.assert_called_once()
            
    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd"))
    def test_execute_error(self, mock_run, temp_config_file):
        runner = BwrapRunner(temp_config_file, ["echo", "hello"], False)
        with pytest.raises(subprocess.CalledProcessError):
            runner.execute()
            
    def test_handle_fds_context_manager(self):
        # Create temp files to get real file descriptors
        with tempfile.NamedTemporaryFile() as f1, tempfile.NamedTemporaryFile() as f2:
            paths = [f1.name, f2.name]
            
            # Use the context manager
            with handle_fds(paths) as fds:
                assert len(fds) == 2
                for fd in fds:
                    assert isinstance(fd, int)
                    assert os.fstat(fd)  # Should not raise error
                    
            # Check fds are closed after context exit
            for fd in fds:
                with pytest.raises(OSError):
                    os.fstat(fd)

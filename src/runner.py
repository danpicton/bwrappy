from pathlib import Path
import os
import subprocess
import yaml
from .models import BwrapConfig
from contextlib import contextmanager
from typing import List

@contextmanager
def handle_seccomp_fds(seccomp_paths):
    """Context manager for handling seccomp file descriptors."""
    fds = []
    try:
        for path in seccomp_paths:
            fd = os.open(path, os.O_RDONLY)
            fds.append(fd)
        yield fds
    finally:
        for fd in fds:
            os.close(fd)

class BwrapRunner:
    def __init__(self, config_path: Path, command: List[str], verbose: bool):
        self.config = self._load_config(config_path)
        self.command = command
        self.verbose = verbose
        self.seccomp_fds = []

    def _load_config(self, path: Path) -> BwrapConfig:
        if not path.exists():
            raise FileNotFoundError(f"Config file '{path}' does not exist.")
        with open(path, 'r') as f:
            try:
                yaml_content = yaml.safe_load(f)
                return BwrapConfig(**yaml_content)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML format: {e}")
            except ValidationError as e:
                raise ValueError(f"Invalid config values: {e}")
    def _build_args(self) -> List[str]:
        args = ["bwrap"]
        for ns in self.config.namespaces.unshare:
            args.append(f"--unshare-{ns}")
        for ns in self.config.namespaces.share:
            args.append(f"--share-{ns}")
        for uid_map in self.config.id_mappings.get("uid", []):
            args.extend(["--map-uid", f"{uid_map.host}:{uid_map.container}"])
        for gid_map in self.config.id_mappings.get("gid", []):
            args.extend(["--map-gid", f"{gid_map.host}:{gid_map.container}"])
    
        # Explicitly handle `special` mounts like proc and dev
        for special_mount in self.config.mounts.get("special", []):
            if special_mount.get("type") == "proc":
                args.extend(["--proc", special_mount["dest"]])
            elif special_mount.get("type") == "dev":
                args.extend(["--dev", special_mount["dest"]])
    
        for bind in self.config.mounts.get("binds", []):
            arg_map = {
                "ro": "--ro-bind",
                "dev": "--dev-bind",
                "proc": "--proc",
                "rbind": "--rbind"
            }
            args.extend([arg_map[bind["type"]], bind["src"], bind["dest"]])
    
        for tmpfs_dir in self.config.mounts.get("tmpfs", []):
            args.extend(["--tmpfs", tmpfs_dir])
        for k, v in self.config.env.get("set", {}).items():
            args.extend(["--setenv", k, v])
        for var in self.config.env.get("unset", []):
            args.extend(["--unsetenv", var])
        for cap in self.config.security.caps_add:
            args.extend(["--cap-add", cap])
        for cap in self.config.security.caps_drop:
            args.extend(["--cap-drop", cap])
        args.extend(self.command)
        
        # output command if verbose
        if self.verbose:
            print("Generated command:", " ".join(args))
    
        return args

    def execute(self):
        with handle_seccomp_fds(self.config.security.seccomp) as seccomp_fds:
            args = self._build_args()
            args = [str(fd) if isinstance(fd, int) else fd for fd in args]
            subprocess.run(args, pass_fds=seccomp_fds, check=True, text=True)

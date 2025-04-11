from pathlib import Path
import os
import subprocess
import yaml
from .models import BwrapConfig, OverlayConfig, FileOperation
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import fcntl
import json
import re

@contextmanager
def handle_fds(fd_paths, mode=os.O_RDONLY):
    """Context manager for handling file descriptors."""
    fds = []
    try:
        for path in fd_paths:
            fd = os.open(path, mode)
            fds.append(fd)
        yield fds
    finally:
        for fd in fds:
            os.close(fd)

class EnvVarLoader(yaml.SafeLoader):
    """Custom YAML loader that substitutes environment variables in strings."""
    
    # Pattern to match environment variables: ${VAR} or $VAR
    ENV_VAR_PATTERN = re.compile(r'(?:\$\{([^}^{]+)\})|(?:\$([a-zA-Z0-9_]+))')
    
    def construct_scalar(self, node):
        """Override construct_scalar to replace environment variables in string values."""
        value = super().construct_scalar(node)
        if isinstance(value, str):
            return self._replace_env_vars(value)
        return value
    
    def _replace_env_vars(self, value):
        """Replace environment variables in a string using the ${VAR} or $VAR syntax."""
        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            # Return the environment variable value or empty string if not found
            return os.environ.get(var_name, '')
            
        return self.ENV_VAR_PATTERN.sub(replace_var, value)

class BwrapRunner:
    def __init__(self, config_paths: List[Path], command: List[str], verbose: bool):
        self.config_paths = config_paths if isinstance(config_paths, list) else [config_paths]
        self.config = self._load_and_merge_configs(self.config_paths)
        self.command = command
        self.verbose = verbose
        self.seccomp_fds = []
        self.fd_map = {}  # Keep track of file descriptors

    def _load_config(self, path: Path) -> dict:
        """Load a single config file and return its contents as a dict with env var substitution."""
        if not path.exists():
            raise FileNotFoundError(f"Config file '{path}' does not exist.")
        with open(path, 'r') as f:
            try:
                # Use the custom EnvVarLoader for environment variable substitution
                return yaml.load(f, Loader=EnvVarLoader) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML format in {path}: {e}")

    def _load_and_merge_configs(self, paths: List[Path]) -> BwrapConfig:
        """Load multiple config files and merge them into a single config."""
        if not paths:
            raise ValueError("At least one config file must be provided.")
            
        merged_dict = {}
        for path in paths:
            config_dict = self._load_config(path)
            self._deep_merge(merged_dict, config_dict)
        
        try:
            return BwrapConfig(**merged_dict)
        except Exception as e:
            raise ValueError(f"Invalid config values after merging: {e}")

    def _deep_merge(self, target: dict, source: dict):
        """
        Deep merge source dict into target dict with special handling for lists and mount configs.
        """
        for key, value in source.items():
            if key not in target:
                target[key] = value
            elif isinstance(target[key], dict) and isinstance(value, dict):
                # Special handling for mounts section
                if key == 'mounts':
                    for mount_type, mount_list in value.items():
                        if mount_type not in target[key]:
                            target[key][mount_type] = mount_list
                        else:
                            # For mount lists, deduplicate by destination path
                            self._merge_by_path(target[key][mount_type], mount_list)
                elif key == 'env' and 'set' in value:
                    # For env.set, update the dict
                    if 'set' not in target[key]:
                        target[key]['set'] = {}
                    target[key]['set'].update(value.get('set', {}))
                    
                    # Handle other env fields
                    for env_key in ['unset', 'clear']:
                        if env_key in value:
                            target[key][env_key] = value[env_key]
                else:
                    # Standard dict merge
                    self._deep_merge(target[key], value)
            elif isinstance(target[key], list) and isinstance(value, list):
                if key in ['overlays', 'file_ops'] or (key == 'binds' and 'dest' in value[0] if value else False):
                    # Merge items by dest path for overlays and file operations
                    self._merge_by_path(target[key], value)
                elif key in ['unshare', 'share', 'seccomp', 'add_seccomp_fd', 
                           'caps_add', 'caps_drop', 'lock_files', 'unset']:
                    # For simple lists, eliminate duplicates
                    target[key] = list(dict.fromkeys(target[key] + value))
                else:
                    # Default is to append with deduplication for simple values
                    target[key] = list(dict.fromkeys(target[key] + value))
            else:
                # For other values (booleans, strings, etc.), later values override earlier ones
                target[key] = value

    def _merge_by_path(self, target_list: list, source_list: list):
        """
        Merge two lists of items by 'dest' path, replacing existing items.
        For items that have a 'dest' field (mounts, overlays, file operations).
        """
        # Build lookup of existing items by dest path
        path_map = {}
        for i, item in enumerate(target_list):
            if isinstance(item, dict) and 'dest' in item:
                path_map[item['dest']] = i
        
        # Merge in new items, replacing existing ones with same dest
        for item in source_list:
            if isinstance(item, dict) and 'dest' in item:
                if item['dest'] in path_map:
                    target_list[path_map[item['dest']]] = item
                else:
                    target_list.append(item)
            else:
                # If item lacks 'dest', just append it
                target_list.append(item)

    def _build_args(self) -> List[str]:
        args = ["bwrap"]
        
        # General options
        if self.config.general.args_fd is not None:
            args.extend(["--args", str(self.config.general.args_fd)])
        
        if self.config.general.argv0:
            args.extend(["--argv0", self.config.general.argv0])
        
        if self.config.general.level_prefix:
            args.append("--level-prefix")
        
        # Namespace options
        for ns in self.config.namespaces.unshare:
            if ns == "all":
                args.append("--unshare-all")
            else:
                args.append(f"--unshare-{ns}")
        
        for ns in self.config.namespaces.share:
            args.append(f"--share-{ns}")
        
        if self.config.namespaces.userns is not None:
            args.extend(["--userns", str(self.config.namespaces.userns)])
        
        if self.config.namespaces.userns2 is not None:
            args.extend(["--userns2", str(self.config.namespaces.userns2)])
        
        if self.config.namespaces.pidns is not None:
            args.extend(["--pidns", str(self.config.namespaces.pidns)])
        
        if self.config.namespaces.disable_userns:
            args.append("--disable-userns")
        
        if self.config.namespaces.assert_userns_disabled:
            args.append("--assert-userns-disabled")
        
        if self.config.namespaces.hostname:
            args.extend(["--hostname", self.config.namespaces.hostname])
        
        # ID mapping
        for uid_map in self.config.id_mappings.get("uid", []):
            args.extend(["--uid", str(uid_map.host)])
            
        for gid_map in self.config.id_mappings.get("gid", []):
            args.extend(["--gid", str(gid_map.host)])
        
        # Environment setup
        if self.config.chdir:
            args.extend(["--chdir", self.config.chdir])
        
        if self.config.env.clear:
            args.append("--clearenv")
        
        for k, v in self.config.env.set.items():
            args.extend(["--setenv", k, v])
        
        for var in self.config.env.unset:
            args.extend(["--unsetenv", var])
        
        # Monitoring
        for lock_file in self.config.monitor.lock_files:
            args.extend(["--lock-file", lock_file])
        
        if self.config.monitor.sync_fd is not None:
            args.extend(["--sync-fd", str(self.config.monitor.sync_fd)])
        
        # Filesystem operations
        for bind in self.config.mounts.get("binds", []):
            bind_type = bind.get("type", "")
            
            # Handle perms and size if they're set
            if self.config.perms:
                args.extend(["--perms", self.config.perms])
            
            if self.config.size and bind_type == "tmpfs":
                args.extend(["--size", str(self.config.size)])
            
            # Handle different bind types
            if bind_type == "ro":
                args.extend(["--ro-bind", bind["src"], bind["dest"]])
            elif bind_type == "dev":
                args.extend(["--dev-bind", bind["src"], bind["dest"]])
            elif bind_type == "proc":
                args.extend(["--proc", bind["dest"]])
            elif bind_type == "rbind":
                args.extend(["--rbind", bind["src"], bind["dest"]])
            elif bind_type == "tmpfs":
                args.extend(["--tmpfs", bind["dest"]])
            elif bind_type == "try":
                args.extend(["--bind-try", bind["src"], bind["dest"]])
            elif bind_type == "dev-try":
                args.extend(["--dev-bind-try", bind["src"], bind["dest"]])
            elif bind_type == "ro-try":
                args.extend(["--ro-bind-try", bind["src"], bind["dest"]])
            elif bind_type == "remount-ro":
                args.extend(["--remount-ro", bind["dest"]])
            elif bind_type == "mqueue":
                args.extend(["--mqueue", bind["dest"]])
            else:
                # Default bind
                args.extend(["--bind", bind["src"], bind["dest"]])
        
        # Handle dev mount
        for dev in self.config.mounts.get("dev", []):
            args.extend(["--dev", dev])
        
        # Handle tmpfs mounts
        for tmpfs in self.config.mounts.get("tmpfs", []):
            if self.config.perms:
                args.extend(["--perms", self.config.perms])
            if self.config.size:
                args.extend(["--size", str(self.config.size)])
            args.extend(["--tmpfs", tmpfs])
        
        # Handle overlay mounts
        for overlay in self.config.overlays:
            for src in overlay.sources:
                args.extend(["--overlay-src", src])
            
            if overlay.type == "overlay":
                args.extend(["--overlay", overlay.rwsrc, overlay.workdir, overlay.dest])
            elif overlay.type == "tmp-overlay":
                args.extend(["--tmp-overlay", overlay.dest])
            elif overlay.type == "ro-overlay":
                args.extend(["--ro-overlay", overlay.dest])
        
        # Handle file operations
        for op in self.config.file_ops:
            if self.config.perms and op.mode is None:
                args.extend(["--perms", self.config.perms])
            elif op.mode:
                args.extend(["--perms", op.mode])
            
            if op.type == "file":
                args.extend(["--file", str(op.src), op.dest])
            elif op.type == "bind-data":
                args.extend(["--bind-data", str(op.src), op.dest])
            elif op.type == "ro-bind-data":
                args.extend(["--ro-bind-data", str(op.src), op.dest])
            elif op.type == "symlink":
                args.extend(["--symlink", op.src, op.dest])
            elif op.type == "chmod":
                args.extend(["--chmod", op.mode, op.dest])
            elif op.type == "dir":
                args.extend(["--dir", op.dest])
        
        # Security options
        for fd in self.config.security.seccomp:
            args.extend(["--seccomp", str(fd)])
            self.seccomp_fds.append(fd)
        
        for fd in self.config.security.add_seccomp_fd:
            args.extend(["--add-seccomp-fd", str(fd)])
            self.seccomp_fds.append(fd)
        
        if self.config.security.exec_label:
            args.extend(["--exec-label", self.config.security.exec_label])
        
        if self.config.security.file_label:
            args.extend(["--file-label", self.config.security.file_label])
        
        if self.config.security.block_fd is not None:
            args.extend(["--block-fd", str(self.config.security.block_fd)])
        
        if self.config.security.userns_block_fd is not None:
            args.extend(["--userns-block-fd", str(self.config.security.userns_block_fd)])
        
        if self.config.security.info_fd is not None:
            args.extend(["--info-fd", str(self.config.security.info_fd)])
        
        if self.config.security.json_status_fd is not None:
            args.extend(["--json-status-fd", str(self.config.security.json_status_fd)])
        
        if self.config.security.new_session:
            args.append("--new-session")
        
        if self.config.security.die_with_parent:
            args.append("--die-with-parent")
        
        if self.config.security.as_pid_1:
            args.append("--as-pid-1")
        
        for cap in self.config.security.caps_add:
            args.extend(["--cap-add", cap])
        
        for cap in self.config.security.caps_drop:
            args.extend(["--cap-drop", cap])
        
        args.extend(self.command)
        
        if self.verbose:
            print("Generated command:", " ".join(args))
        
        return args
    
    def _prepare_file_descriptors(self):
        """Prepare and open file descriptors needed for execution."""
        fd_list = []
        
        # Handle seccomp file paths
        for path in self.config.security.seccomp:
            if isinstance(path, str):
                fd = os.open(path, os.O_RDONLY)
                self.fd_map[path] = fd
                fd_list.append(fd)
        
        # Handle seccomp FDs
        fd_list.extend(self.config.security.add_seccomp_fd)
        
        # Handle other FDs
        if self.config.security.block_fd is not None:
            fd_list.append(self.config.security.block_fd)
        
        if self.config.security.userns_block_fd is not None:
            fd_list.append(self.config.security.userns_block_fd)
        
        if self.config.security.info_fd is not None:
            fd_list.append(self.config.security.info_fd)
        
        if self.config.security.json_status_fd is not None:
            fd_list.append(self.config.security.json_status_fd)
        
        if self.config.monitor.sync_fd is not None:
            fd_list.append(self.config.monitor.sync_fd)
        
        if self.config.general.args_fd is not None:
            fd_list.append(self.config.general.args_fd)
        
        # Handle file operation FDs
        for op in self.config.file_ops:
            if op.type in ["file", "bind-data", "ro-bind-data"] and isinstance(op.src, int):
                fd_list.append(op.src)
        
        return fd_list
    
    def _cleanup_file_descriptors(self):
        """Close any file descriptors we opened."""
        for fd in self.fd_map.values():
            os.close(fd)
        self.fd_map.clear()
    
    def execute(self):
        try:
            args = self._build_args()
            pass_fds = self._prepare_file_descriptors()
            
            # Convert any file descriptor integers to strings
            args = [str(arg) if isinstance(arg, int) else arg for arg in args]
            
            result = subprocess.run(
                args, 
                pass_fds=pass_fds,
                check=True, 
                text=True
            )
            
            return result
        except subprocess.CalledProcessError as e:
            raise e
        finally:
            self._cleanup_file_descriptors()


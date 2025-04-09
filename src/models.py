from pydantic import BaseModel, model_validator, Field
from typing import List, Optional, Dict, Literal, Union, Any

class BindMount(BaseModel):
    type: Optional[Literal["ro", "dev", "proc", "rbind", "tmpfs", "try", 
                          "dev-try", "ro-try", "remount-ro", "mqueue"]] = None
    src: Optional[str] = None
    dest: str

class UidMap(BaseModel):
    host: int
    container: int

class NamespaceConfig(BaseModel):
    unshare: List[Literal["ipc", "net", "pid", "user", "user-try", "uts", "cgroup", "cgroup-try", "all"]] = []
    share: List[Literal["ipc", "net", "pid", "user", "uts", "cgroup"]] = []
    userns: Optional[int] = None
    userns2: Optional[int] = None
    pidns: Optional[int] = None
    disable_userns: bool = False
    assert_userns_disabled: bool = False
    hostname: Optional[str] = None

class SecurityConfig(BaseModel):
    seccomp: List[str] = []
    add_seccomp_fd: List[int] = []
    caps_add: List[str] = []
    caps_drop: List[str] = []
    exec_label: Optional[str] = None
    file_label: Optional[str] = None
    block_fd: Optional[int] = None
    userns_block_fd: Optional[int] = None
    info_fd: Optional[int] = None
    json_status_fd: Optional[int] = None
    new_session: bool = False
    die_with_parent: bool = False
    as_pid_1: bool = False

class OverlayConfig(BaseModel):
    type: Literal["overlay", "tmp-overlay", "ro-overlay"]
    sources: List[str] = []
    rwsrc: Optional[str] = None
    workdir: Optional[str] = None
    dest: str

class FileOperation(BaseModel):
    type: Literal["file", "bind-data", "ro-bind-data", "symlink", "chmod", "dir"]
    src: Optional[Union[int, str]] = None
    dest: str
    mode: Optional[str] = None

class GeneralConfig(BaseModel):
    args_fd: Optional[int] = None
    argv0: Optional[str] = None
    level_prefix: bool = False

class MonitorConfig(BaseModel):
    lock_files: List[str] = []
    sync_fd: Optional[int] = None

class EnvConfig(BaseModel):
    set: Dict[str, str] = {}
    unset: List[str] = []
    clear: bool = False

class BwrapConfig(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    namespaces: NamespaceConfig = Field(default_factory=NamespaceConfig)
    mounts: Dict[str, List[Any]] = {}
    overlays: List[OverlayConfig] = []
    file_ops: List[FileOperation] = []
    id_mappings: Dict[str, List[UidMap]] = {}
    env: EnvConfig = Field(default_factory=EnvConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    perms: Optional[str] = None
    size: Optional[int] = None
    chdir: Optional[str] = None

    @model_validator(mode='after')
    def validate_mounts(cls, values):
        if 'binds' in values.mounts:
            for bind in values.mounts.get('binds', []):
                if bind.get("type") == "tmpfs" and bind.get("src"):
                    raise ValueError("tmpfs mounts don't use src")
                
                if "try" in str(bind.get("type", "")) and not bind.get("src"):
                    raise ValueError(f"{bind.get('type')} requires a source")
                
        if values.namespaces.disable_userns and "user" not in values.namespaces.unshare:
            raise ValueError("--disable-userns requires --unshare-user")

        for overlay in values.overlays:
            if overlay.type == "overlay" and (not overlay.rwsrc or not overlay.workdir):
                raise ValueError("overlay requires rwsrc and workdir")
            if overlay.type == "ro-overlay" and len(overlay.sources) < 2:
                raise ValueError("ro-overlay requires at least two overlay-src")

        return values


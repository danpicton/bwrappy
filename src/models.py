from pydantic import BaseModel, model_validator
from typing import List, Optional, Dict, Literal

class BindMount(BaseModel):
    type: Literal["ro", "dev", "proc", "rbind", "tmpfs"]
    src: str
    dest: str

class UidMap(BaseModel):
    host: int
    container: int

class NamespaceConfig(BaseModel):
    unshare: List[Literal["ipc", "network", "pid", "user", "uts", "cgroup"]] = []
    share: List[Literal["ipc", "network", "pid", "user", "uts", "cgroup"]] = []

class SecurityConfig(BaseModel):
    self_protection: Optional[bool] = False
    seccomp: List[str] = []
    caps_add: List[str] = []
    caps_drop: List[str] = []

class BwrapConfig(BaseModel):
    namespaces: NamespaceConfig = NamespaceConfig()
    mounts: Dict[str, List] = {}
    id_mappings: Dict[str, List[UidMap]] = {}
    env: Dict[str, Dict] = {}
    security: SecurityConfig = SecurityConfig()

    @model_validator(mode='after')
    def validate_mounts(cls, values):
        if 'binds' in values.mounts:
            for bind in values.mounts['binds']:
                if bind.get("type") == "tmpfs" and bind.get("src"):
                    raise ValueError("tmpfs mounts don't use src")
        return values

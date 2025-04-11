import pytest
from pathlib import Path
import os
from src.models import (
    BindMount, UidMap, NamespaceConfig, SecurityConfig, 
    OverlayConfig, FileOperation, BwrapConfig
)
from pydantic import ValidationError

class TestModels:
    def test_bind_mount_validation(self):
        # Valid bind mounts
        BindMount(src="/src", dest="/dest")
        BindMount(type="ro", src="/src", dest="/dest")
        BindMount(type="dev", src="/src", dest="/dest")
        BindMount(type="proc", dest="/proc")
        BindMount(type="tmpfs", dest="/tmp")
        
        # Invalid types
        with pytest.raises(ValidationError):
            BindMount(type="invalid", src="/src", dest="/dest")
        
        # Missing dest
        with pytest.raises(ValidationError):
            BindMount(src="/src")
            
    def test_uid_map_validation(self):
        # Valid uid maps
        UidMap(host=1000, container=0)
        
        # Invalid (missing fields)
        with pytest.raises(ValidationError):
            UidMap(host=1000)
            
    def test_namespace_config_validation(self):
        # Valid namespaces
        NamespaceConfig(unshare=["ipc", "net", "pid"])
        NamespaceConfig(share=["net"])
        NamespaceConfig(unshare=["all"])
        
        # Invalid namespace type
        with pytest.raises(ValidationError):
            NamespaceConfig(unshare=["invalid"])
            
    def test_security_config_validation(self):
        # Valid security configs
        SecurityConfig()
        SecurityConfig(caps_add=["CAP_NET_ADMIN"])
        SecurityConfig(caps_drop=["ALL"])
        
    def test_overlay_config_validation(self):
        # Valid overlay configs
        OverlayConfig(type="overlay", sources=["/src1", "/src2"], 
                      rwsrc="/rw", workdir="/work", dest="/dest")
        OverlayConfig(type="tmp-overlay", sources=["/src1", "/src2"], dest="/dest")
        OverlayConfig(type="ro-overlay", sources=["/src1", "/src2"], dest="/dest")
        
        # Missing required fields
        with pytest.raises(ValidationError):
            OverlayConfig(type="overlay", sources=["/src"])
            
        # Invalid type
        with pytest.raises(ValidationError):
            OverlayConfig(type="invalid", sources=["/src"], dest="/dest")
            
    def test_file_operation_validation(self):
        # Valid file operations
        FileOperation(type="file", src=5, dest="/dest")
        FileOperation(type="bind-data", src=5, dest="/dest")
        FileOperation(type="symlink", src="/target", dest="/link")
        FileOperation(type="chmod", mode="0755", dest="/file")
        FileOperation(type="dir", dest="/dir")
        
        # Invalid type
        with pytest.raises(ValidationError):
            FileOperation(type="invalid", dest="/dest")
            
    def test_bwrap_config_validation(self):
        # Basic valid config
        BwrapConfig()
        
        # Simple config with some options
        BwrapConfig(
            namespaces=NamespaceConfig(unshare=["net", "pid"]),
            mounts={
                "binds": [
                    {"type": "ro", "src": "/src", "dest": "/dest"}
                ],
                "tmpfs": ["/tmp"]
            }
        )
        
        # Test TMPFS validation
        with pytest.raises(ValueError):
            BwrapConfig(
                mounts={
                    "binds": [
                        {"type": "tmpfs", "src": "/src", "dest": "/dest"}
                    ]
                }
            )
            
        # Test ro-overlay validation
        with pytest.raises(ValueError):
            BwrapConfig(
                overlays=[
                    OverlayConfig(type="ro-overlay", sources=["/src1"], dest="/dest")
                ]
            )

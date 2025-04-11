# bwrappy 

bwrappy is a convenient YAML-based configuration wrapper for Bubblewrap (`bwrap`), a sandbox utility that leverages Linux namespaces to create isolated environments for running applications.

## Features

- **YAML Configuration:** Define your sandbox environments in human-readable YAML files
- **Configuration Stacking:** Combine and override configurations by stacking multiple YAML files
- **Environment Variable Substitution:** Use `$VAR` or `${VAR}` syntax in configs to incorporate environment variables
- **Complete Bubblewrap Support:** Supports the full range of Bubblewrap's functionality

## Installation

Ensure you have Bubblewrap installed on your system first:

```bash
# For Debian/Ubuntu
sudo apt install bubblewrap

# For Fedora/RHEL
sudo dnf install bubblewrap

# For Arch Linux
sudo pacman -S bubblewrap
```

Then install bwrappy:

```bash
git clone https://github.com/yourusername/bwrappy.git
cd bwrappy
pip install -e .
```

## Usage

Create a YAML configuration file that defines your sandbox environment:

```yaml
# basic.yaml
namespaces:
  share:
    - net
  unshare:
    - ipc
    - pid
mounts:
  binds:
    - type: ro
      src: /etc/passwd
      dest: /etc/passwd
    - type: ro
      src: /usr/bin
      dest: /usr/bin
    - type: ro
      src: /lib
      dest: /lib
    - type: ro
      src: /lib64
      dest: /lib64
    - type: proc
      dest: /proc
    - type: dev
      src: /dev
      dest: /dev
  tmpfs:
    - /tmp
env:
  set:
    APP_ENV: sandbox
```

Run a command inside the sandbox:

```bash
python main.py -c basic.yaml echo "Hello from the sandbox!"
```

### Stacking Configurations

You can combine multiple configuration files, with later files taking precedence over earlier ones:

```bash
python main.py -c base.yaml -c app-specific.yaml myapp --option value
```

### Environment Variable Substitution

You can use environment variables in your YAML configurations:

```yaml
# dev-env.yaml
mounts:
  binds:
    - type: bind
      src: ${HOME}/projects
      dest: /projects
    - type: ro
      src: $HOME/.config/app
      dest: /app/config
```

### Verbose Mode

To see the generated Bubblewrap command:

```bash
python main.py -v -c config.yaml ls -la
```

## Configuration Reference

### Namespaces

Control which Linux namespaces to use:

```yaml
namespaces:
  unshare:
    - ipc
    - pid
    - net
    - user
  share:
    - net
  userns: 5  # User namespace FD
  hostname: sandbox
```

### Mounts

Define filesystem mounts:

```yaml
mounts:
  binds:
    - type: ro  # Read-only bind mount
      src: /etc
      dest: /etc
    - type: dev  # Device bind mount
      src: /dev
      dest: /dev
    - type: proc  # Procfs
      dest: /proc
    - type: tmpfs  # Tmpfs
      dest: /tmp
    - type: rbind  # Recursive bind
      src: /home/user
      dest: /home
  tmpfs:
    - /var/tmp
    - /run
```

### Overlays

Create overlay filesystems:

```yaml
overlays:
  - type: overlay
    sources:
      - /lower1
      - /lower2
    rwsrc: /upper
    workdir: /work
    dest: /merged
  - type: tmp-overlay  # Temporary overlay
    sources:
      - /lower
    dest: /merged
```

### File Operations

Perform file operations inside the sandbox:

```yaml
file_ops:
  - type: dir
    dest: /app/data
  - type: symlink
    src: /target
    dest: /link
  - type: file
    src: 3  # File descriptor
    dest: /app/config
  - type: chmod
    mode: "0755"
    dest: /app/script.sh
```

### Environment Control

Manage environment variables:

```yaml
env:
  clear: true  # Clear all env vars
  set:
    APP_ENV: production
    DEBUG: "false"
  unset:
    - TEMP_VAR
```

### Security Settings

Configure security features:

```yaml
security:
  caps_drop:
    - ALL
  caps_add:
    - CAP_NET_ADMIN
  new_session: true
  die_with_parent: true
```

### ID Mappings

Map user and group IDs:

```yaml
id_mappings:
  uid:
    - host: 1000
      container: 0
  gid:
    - host: 1000
      container: 0
```

## Development

### Running Tests

```bash
# Run unit tests
pytest

# Run integration tests (requires root for some features)
pytest --run-integration
```

## License

<insert license here>

## Acknowledgements

bwrappy is built around [Bubblewrap](https://github.com/containers/bubblewrap), the excellent sandbox utility developed by the GNOME Project.

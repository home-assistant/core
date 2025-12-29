"""Go2rtc utility functions."""

from pathlib import Path

_HA_MANAGED_UNIX_SOCKET_FILE = "go2rtc.sock"


def get_go2rtc_unix_socket_path(path: str | Path) -> str:
    """Get the Go2rtc unix socket path."""
    if not isinstance(path, Path):
        path = Path(path)
    return str(path / _HA_MANAGED_UNIX_SOCKET_FILE)

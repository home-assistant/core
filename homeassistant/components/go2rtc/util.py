"""Go2rtc utility functions."""

from pathlib import Path
import string
from urllib.parse import quote

from homeassistant.components.camera import Camera

_HA_MANAGED_UNIX_SOCKET_FILE = "go2rtc.sock"
# Go2rtc is not validating the camera identifier, but some characters (e.g. : or #)
# have special meaning in URLs and could cause issues.
_SAFE_CHARS = string.ascii_letters + string.digits + "._-"


def get_go2rtc_unix_socket_path(path: str | Path) -> str:
    """Get the Go2rtc unix socket path."""
    if not isinstance(path, Path):
        path = Path(path)
    return str(path / _HA_MANAGED_UNIX_SOCKET_FILE)


def get_camera_identifier(camera: Camera) -> str:
    """Get the Go2rtc camera identifier."""
    attr = camera.entity_id
    if camera.unique_id is not None:
        attr = f"{camera.platform.platform_name}_{camera.unique_id}"
    return quote(attr, safe=_SAFE_CHARS)

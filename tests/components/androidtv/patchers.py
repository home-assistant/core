"""Define patches used for androidtv tests."""

from socket import error as socket_error
from unittest.mock import patch


def connect_device_success(self, *args, **kwargs):
    """Return `self`, which will result in the ADB connection being interpreted as available."""
    return self


def connect_device_fail(self, *args, **kwargs):
    """Raise a socket error."""
    raise socket_error


def adb_shell_python_adb_error(self, cmd):
    """Raise an error that is among those caught for the Python ADB implementation."""
    raise AttributeError


def adb_shell_adb_server_error(self, cmd):
    """Raise an error that is among those caught for the ADB server implementation."""
    raise ConnectionResetError


class AdbAvailable:
    """A class that indicates the ADB connection is available."""

    def shell(self, cmd):
        """Send an ADB shell command (ADB server implementation)."""
        return ""


class AdbUnavailable:
    """A class with ADB shell methods that raise errors."""

    def __bool__(self):
        """Return `False` to indicate that the ADB connection is unavailable."""
        return False

    def shell(self, cmd):
        """Raise an error that pertains to the Python ADB implementation."""
        raise ConnectionResetError


PATCH_PYTHON_ADB_CONNECT_SUCCESS = patch(
    "adb.adb_commands.AdbCommands.ConnectDevice", connect_device_success
)
PATCH_PYTHON_ADB_COMMAND_SUCCESS = patch(
    "adb.adb_commands.AdbCommands.Shell", return_value=""
)
PATCH_PYTHON_ADB_CONNECT_FAIL = patch(
    "adb.adb_commands.AdbCommands.ConnectDevice", connect_device_fail
)
PATCH_PYTHON_ADB_COMMAND_FAIL = patch(
    "adb.adb_commands.AdbCommands.Shell", adb_shell_python_adb_error
)
PATCH_PYTHON_ADB_COMMAND_NONE = patch(
    "adb.adb_commands.AdbCommands.Shell", return_value=None
)

PATCH_ADB_SERVER_CONNECT_SUCCESS = patch(
    "adb_messenger.client.Client.device", return_value=AdbAvailable()
)
PATCH_ADB_SERVER_AVAILABLE = patch(
    "androidtv.basetv.BaseTV.available", return_value=True
)
PATCH_ADB_SERVER_CONNECT_FAIL = patch(
    "adb_messenger.client.Client.device", return_value=AdbUnavailable()
)
PATCH_ADB_SERVER_COMMAND_FAIL = patch(
    "{}.AdbAvailable.shell".format(__name__), adb_shell_adb_server_error
)
PATCH_ADB_SERVER_COMMAND_NONE = patch(
    "{}.AdbAvailable.shell".format(__name__), return_value=None
)

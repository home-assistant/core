"""Define patches used for androidtv tests."""

from socket import error as socket_error
from unittest.mock import mock_open, patch


class AdbDeviceFake:
    """A fake of the `adb_shell.adb_device.AdbDevice` class."""

    def __init__(self, *args, **kwargs):
        """Initialize a fake `adb_shell.adb_device.AdbDevice` instance."""
        self.available = False

    def close(self):
        """Close the socket connection."""
        self.available = False

    def connect(self, *args, **kwargs):
        """Try to connect to a device."""
        raise NotImplementedError

    def shell(self, cmd):
        """Send an ADB shell command."""
        return None


class ClientFakeSuccess:
    """A fake of the `adb_messenger.client.Client` class when the connection and shell commands succeed."""

    def __init__(self, host="127.0.0.1", port=5037):
        """Initialize a `ClientFakeSuccess` instance."""
        self._devices = []

    def devices(self):
        """Get a list of the connected devices."""
        return self._devices

    def device(self, serial):
        """Mock the `Client.device` method when the device is connected via ADB."""
        device = DeviceFake(serial)
        self._devices.append(device)
        return device


class ClientFakeFail:
    """A fake of the `adb_messenger.client.Client` class when the connection and shell commands fail."""

    def __init__(self, host="127.0.0.1", port=5037):
        """Initialize a `ClientFakeFail` instance."""
        self._devices = []

    def devices(self):
        """Get a list of the connected devices."""
        return self._devices

    def device(self, serial):
        """Mock the `Client.device` method when the device is not connected via ADB."""
        self._devices = []


class DeviceFake:
    """A fake of the `adb_messenger.device.Device` class."""

    def __init__(self, host):
        """Initialize a `DeviceFake` instance."""
        self.host = host

    def get_serial_no(self):
        """Get the serial number for the device (IP:PORT)."""
        return self.host

    def shell(self, cmd):
        """Send an ADB shell command."""
        raise NotImplementedError


def patch_connect(success):
    """Mock the `adb_shell.adb_device.AdbDevice` and `adb_messenger.client.Client` classes."""

    def connect_success_python(self, *args, **kwargs):
        """Mock the `AdbDeviceFake.connect` method when it succeeds."""
        self.available = True

    def connect_fail_python(self, *args, **kwargs):
        """Mock the `AdbDeviceFake.connect` method when it fails."""
        raise socket_error

    if success:
        return {
            "python": patch(
                f"{__name__}.AdbDeviceFake.connect", connect_success_python
            ),
            "server": patch("androidtv.adb_manager.Client", ClientFakeSuccess),
        }
    return {
        "python": patch(f"{__name__}.AdbDeviceFake.connect", connect_fail_python),
        "server": patch("androidtv.adb_manager.Client", ClientFakeFail),
    }


def patch_shell(response=None, error=False):
    """Mock the `AdbDeviceFake.shell` and `DeviceFake.shell` methods."""

    def shell_success(self, cmd):
        """Mock the `AdbDeviceFake.shell` and `DeviceFake.shell` methods when they are successful."""
        self.shell_cmd = cmd
        return response

    def shell_fail_python(self, cmd):
        """Mock the `AdbDeviceFake.shell` method when it fails."""
        self.shell_cmd = cmd
        raise AttributeError

    def shell_fail_server(self, cmd):
        """Mock the `DeviceFake.shell` method when it fails."""
        self.shell_cmd = cmd
        raise ConnectionResetError

    if not error:
        return {
            "python": patch(f"{__name__}.AdbDeviceFake.shell", shell_success),
            "server": patch(f"{__name__}.DeviceFake.shell", shell_success),
        }
    return {
        "python": patch(f"{__name__}.AdbDeviceFake.shell", shell_fail_python),
        "server": patch(f"{__name__}.DeviceFake.shell", shell_fail_server),
    }


PATCH_ADB_DEVICE = patch("androidtv.adb_manager.AdbDevice", AdbDeviceFake)
PATCH_ANDROIDTV_OPEN = patch("androidtv.adb_manager.open", mock_open())
PATCH_KEYGEN = patch("homeassistant.components.androidtv.media_player.keygen")
PATCH_SIGNER = patch("androidtv.adb_manager.PythonRSASigner")


def isfile(filepath):
    """Mock `os.path.isfile`."""
    return filepath.endswith("adbkey")


PATCH_ISFILE = patch("os.path.isfile", isfile)
PATCH_ACCESS = patch("os.access", return_value=True)


def patch_firetv_update(state, current_app, running_apps):
    """Patch the `FireTV.update()` method."""
    return patch(
        "androidtv.firetv.FireTV.update",
        return_value=(state, current_app, running_apps),
    )


PATCH_LAUNCH_APP = patch("androidtv.firetv.FireTV.launch_app")
PATCH_STOP_APP = patch("androidtv.firetv.FireTV.stop_app")

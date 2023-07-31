"""Define patches used for androidtv tests."""
from unittest.mock import patch

from androidtv.constants import CMD_DEVICE_PROPERTIES, CMD_MAC_ETH0, CMD_MAC_WLAN0

from homeassistant.components.androidtv.const import (
    DEFAULT_ADB_SERVER_PORT,
    DEVICE_ANDROIDTV,
    DEVICE_FIRETV,
)

ADB_SERVER_HOST = "127.0.0.1"
KEY_PYTHON = "python"
KEY_SERVER = "server"

ADB_DEVICE_TCP_ASYNC_FAKE = "AdbDeviceTcpAsyncFake"
DEVICE_ASYNC_FAKE = "DeviceAsyncFake"

PROPS_DEV_INFO = "fake\nfake\n0123456\nfake"
PROPS_DEV_MAC = "ether ab:cd:ef:gh:ij:kl brd"


class AdbDeviceTcpAsyncFake:
    """A fake of the `adb_shell.adb_device_async.AdbDeviceTcpAsync` class."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize a fake `adb_shell.adb_device_async.AdbDeviceTcpAsync` instance."""
        self.available = False

    async def close(self):
        """Close the socket connection."""
        self.available = False

    async def connect(self, *args, **kwargs):
        """Try to connect to a device."""
        raise NotImplementedError

    async def shell(self, cmd, *args, **kwargs):
        """Send an ADB shell command."""
        return None


class ClientAsyncFakeSuccess:
    """A fake of the `ClientAsync` class when the connection and shell commands succeed."""

    def __init__(self, host=ADB_SERVER_HOST, port=DEFAULT_ADB_SERVER_PORT) -> None:
        """Initialize a `ClientAsyncFakeSuccess` instance."""
        self._devices = []

    async def device(self, serial):
        """Mock the `ClientAsync.device` method when the device is connected via ADB."""
        device = DeviceAsyncFake(serial)
        self._devices.append(device)
        return device


class ClientAsyncFakeFail:
    """A fake of the `ClientAsync` class when the connection and shell commands fail."""

    def __init__(self, host=ADB_SERVER_HOST, port=DEFAULT_ADB_SERVER_PORT) -> None:
        """Initialize a `ClientAsyncFakeFail` instance."""
        self._devices = []

    async def device(self, serial):
        """Mock the `ClientAsync.device` method when the device is not connected via ADB."""
        self._devices = []
        return None


class DeviceAsyncFake:
    """A fake of the `DeviceAsync` class."""

    def __init__(self, host) -> None:
        """Initialize a `DeviceAsyncFake` instance."""
        self.host = host

    async def shell(self, cmd):
        """Send an ADB shell command."""
        raise NotImplementedError


def patch_connect(success):
    """Mock the `adb_shell.adb_device_async.AdbDeviceTcpAsync` and `ClientAsync` classes."""

    async def connect_success_python(self, *args, **kwargs):
        """Mock the `AdbDeviceTcpAsyncFake.connect` method when it succeeds."""
        self.available = True

    async def connect_fail_python(self, *args, **kwargs):
        """Mock the `AdbDeviceTcpAsyncFake.connect` method when it fails."""
        raise OSError

    if success:
        return {
            KEY_PYTHON: patch(
                f"{__name__}.{ADB_DEVICE_TCP_ASYNC_FAKE}.connect",
                connect_success_python,
            ),
            KEY_SERVER: patch(
                "androidtv.adb_manager.adb_manager_async.ClientAsync",
                ClientAsyncFakeSuccess,
            ),
        }
    return {
        KEY_PYTHON: patch(
            f"{__name__}.{ADB_DEVICE_TCP_ASYNC_FAKE}.connect", connect_fail_python
        ),
        KEY_SERVER: patch(
            "androidtv.adb_manager.adb_manager_async.ClientAsync", ClientAsyncFakeFail
        ),
    }


def patch_shell(response=None, error=False, mac_eth=False, exc=None):
    """Mock the `AdbDeviceTcpAsyncFake.shell` and `DeviceAsyncFake.shell` methods."""

    async def shell_success(self, cmd, *args, **kwargs):
        """Mock the `AdbDeviceTcpAsyncFake.shell` and `DeviceAsyncFake.shell` methods when they are successful."""
        self.shell_cmd = cmd
        if cmd == CMD_DEVICE_PROPERTIES:
            return PROPS_DEV_INFO
        if cmd == CMD_MAC_WLAN0:
            return PROPS_DEV_MAC
        if cmd == CMD_MAC_ETH0:
            return PROPS_DEV_MAC if mac_eth else None
        return response

    async def shell_fail_python(self, cmd, *args, **kwargs):
        """Mock the `AdbDeviceTcpAsyncFake.shell` method when it fails."""
        self.shell_cmd = cmd
        raise exc or ValueError

    async def shell_fail_server(self, cmd):
        """Mock the `DeviceAsyncFake.shell` method when it fails."""
        self.shell_cmd = cmd
        raise ConnectionResetError

    if not error:
        return {
            KEY_PYTHON: patch(
                f"{__name__}.{ADB_DEVICE_TCP_ASYNC_FAKE}.shell", shell_success
            ),
            KEY_SERVER: patch(f"{__name__}.{DEVICE_ASYNC_FAKE}.shell", shell_success),
        }
    return {
        KEY_PYTHON: patch(
            f"{__name__}.{ADB_DEVICE_TCP_ASYNC_FAKE}.shell", shell_fail_python
        ),
        KEY_SERVER: patch(f"{__name__}.{DEVICE_ASYNC_FAKE}.shell", shell_fail_server),
    }


def patch_androidtv_update(
    state,
    current_app,
    running_apps,
    device,
    is_volume_muted,
    volume_level,
    hdmi_input,
):
    """Patch the `AndroidTV.update()` method."""
    return {
        DEVICE_ANDROIDTV: patch(
            "androidtv.androidtv.androidtv_async.AndroidTVAsync.update",
            return_value=(
                state,
                current_app,
                running_apps,
                device,
                is_volume_muted,
                volume_level,
                hdmi_input,
            ),
        ),
        DEVICE_FIRETV: patch(
            "androidtv.firetv.firetv_async.FireTVAsync.update",
            return_value=(state, current_app, running_apps, hdmi_input),
        ),
    }


def isfile(filepath):
    """Mock `os.path.isfile`."""
    return filepath.endswith("adbkey")


PATCH_SCREENCAP = patch(
    "androidtv.basetv.basetv_async.BaseTVAsync.adb_screencap",
    return_value=b"image",
)
PATCH_SETUP_ENTRY = patch(
    "homeassistant.components.androidtv.async_setup_entry",
    return_value=True,
)
PATCH_ACCESS = patch("homeassistant.components.androidtv.os.access", return_value=True)
PATCH_ISFILE = patch("homeassistant.components.androidtv.os.path.isfile", isfile)
PATCH_LAUNCH_APP = patch("androidtv.basetv.basetv_async.BaseTVAsync.launch_app")
PATCH_STOP_APP = patch("androidtv.basetv.basetv_async.BaseTVAsync.stop_app")

# Cause the update to raise an unexpected type of exception
PATCH_ANDROIDTV_UPDATE_EXCEPTION = patch(
    "androidtv.androidtv.androidtv_async.AndroidTVAsync.update",
    side_effect=ZeroDivisionError,
)

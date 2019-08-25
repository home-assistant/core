"""The tests for the androidtv platform."""
import logging
from socket import error as socket_error
import unittest
from unittest.mock import patch

from homeassistant.components.androidtv.media_player import (
    AndroidTVDevice,
    FireTVDevice,
    setup,
)


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


class TestAndroidTVPythonImplementation(unittest.TestCase):
    """Test the androidtv media player for an Android TV device."""

    def setUp(self):
        """Set up an `AndroidTVDevice` media player."""
        with PATCH_PYTHON_ADB_CONNECT_SUCCESS, PATCH_PYTHON_ADB_COMMAND_SUCCESS:
            aftv = setup("IP:PORT", device_class="androidtv")
            self.aftv = AndroidTVDevice(aftv, "Fake Android TV", {}, None, None)

    def test_reconnect(self):
        """Test that the error and reconnection attempts are logged correctly.

        "Handles device/service unavailable. Log a warning once when
        unavailable, log once when reconnected."

        https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
        """
        with self.assertLogs(level=logging.WARNING) as logs:
            with PATCH_PYTHON_ADB_CONNECT_FAIL, PATCH_PYTHON_ADB_COMMAND_FAIL:
                for _ in range(5):
                    self.aftv.update()
                    self.assertFalse(self.aftv.available)
                    self.assertIsNone(self.aftv.state)

        assert len(logs.output) == 2
        assert logs.output[0].startswith("ERROR")
        assert logs.output[1].startswith("WARNING")

        with self.assertLogs(level=logging.DEBUG) as logs:
            with PATCH_PYTHON_ADB_CONNECT_SUCCESS, PATCH_PYTHON_ADB_COMMAND_SUCCESS:
                # Update 1 will reconnect
                self.aftv.update()
                self.assertTrue(self.aftv.available)

                # Update 2 will update the state
                self.aftv.update()
                self.assertTrue(self.aftv.available)
                self.assertIsNotNone(self.aftv.state)

        assert (
            "ADB connection to {} successfully established".format(self.aftv.aftv.host)
            in logs.output[0]
        )

    def test_adb_shell_returns_none(self):
        """Test the case that the ADB shell command returns `None`.

        The state should be `None` and the device should be unavailable.
        """
        with PATCH_PYTHON_ADB_COMMAND_NONE:
            self.aftv.update()
            self.assertFalse(self.aftv.available)
            self.assertIsNone(self.aftv.state)

        with PATCH_PYTHON_ADB_CONNECT_SUCCESS, PATCH_PYTHON_ADB_COMMAND_SUCCESS:
            # Update 1 will reconnect
            self.aftv.update()
            self.assertTrue(self.aftv.available)

            # Update 2 will update the state
            self.aftv.update()
            self.assertTrue(self.aftv.available)
            self.assertIsNotNone(self.aftv.state)


class TestAndroidTVServerImplementation(unittest.TestCase):
    """Test the androidtv media player for an Android TV device."""

    def setUp(self):
        """Set up an `AndroidTVDevice` media player."""
        with PATCH_ADB_SERVER_CONNECT_SUCCESS, PATCH_ADB_SERVER_AVAILABLE:
            aftv = setup(
                "IP:PORT", adb_server_ip="ADB_SERVER_IP", device_class="androidtv"
            )
            self.aftv = AndroidTVDevice(aftv, "Fake Android TV", {}, None, None)

    def test_reconnect(self):
        """Test that the error and reconnection attempts are logged correctly.

        "Handles device/service unavailable. Log a warning once when
        unavailable, log once when reconnected."

        https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
        """
        with self.assertLogs(level=logging.WARNING) as logs:
            with PATCH_ADB_SERVER_CONNECT_FAIL, PATCH_ADB_SERVER_COMMAND_FAIL:
                for _ in range(5):
                    self.aftv.update()
                    self.assertFalse(self.aftv.available)
                    self.assertIsNone(self.aftv.state)

        assert len(logs.output) == 2
        assert logs.output[0].startswith("ERROR")
        assert logs.output[1].startswith("WARNING")

        with self.assertLogs(level=logging.DEBUG) as logs:
            with PATCH_ADB_SERVER_CONNECT_SUCCESS:
                self.aftv.update()
                self.assertTrue(self.aftv.available)
                self.assertIsNotNone(self.aftv.state)

        assert (
            "ADB connection to {} via ADB server {}:{} successfully established".format(
                self.aftv.aftv.host,
                self.aftv.aftv.adb_server_ip,
                self.aftv.aftv.adb_server_port,
            )
            in logs.output[0]
        )

    def test_adb_shell_returns_none(self):
        """Test the case that the ADB shell command returns `None`.

        The state should be `None` and the device should be unavailable.
        """
        with PATCH_ADB_SERVER_COMMAND_NONE:
            self.aftv.update()
            self.assertFalse(self.aftv.available)
            self.assertIsNone(self.aftv.state)

        with PATCH_ADB_SERVER_CONNECT_SUCCESS:
            self.aftv.update()
            self.assertTrue(self.aftv.available)
            self.assertIsNotNone(self.aftv.state)


class TestFireTVPythonImplementation(TestAndroidTVPythonImplementation):
    """Test the androidtv media player for a Fire TV device."""

    def setUp(self):
        """Set up a `FireTVDevice` media player."""
        with PATCH_PYTHON_ADB_CONNECT_SUCCESS, PATCH_PYTHON_ADB_COMMAND_SUCCESS:
            aftv = setup("IP:PORT", device_class="firetv")
            self.aftv = FireTVDevice(aftv, "Fake Fire TV", {}, True, None, None)


class TestFireTVServerImplementation(TestAndroidTVServerImplementation):
    """Test the androidtv media player for a Fire TV device."""

    def setUp(self):
        """Set up a `FireTVDevice` media player."""
        with PATCH_ADB_SERVER_CONNECT_SUCCESS, PATCH_ADB_SERVER_AVAILABLE:
            aftv = setup(
                "IP:PORT", adb_server_ip="ADB_SERVER_IP", device_class="firetv"
            )
            self.aftv = FireTVDevice(aftv, "Fake Fire TV", {}, True, None, None)

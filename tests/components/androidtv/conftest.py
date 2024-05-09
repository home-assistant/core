"""Fixtures for the Android TV integration tests."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from . import patchers


@pytest.fixture(autouse=True)
def adb_device_tcp_fixture() -> Generator[None, patchers.AdbDeviceTcpAsyncFake, None]:
    """Patch ADB Device TCP."""
    with patch(
        "androidtv.adb_manager.adb_manager_async.AdbDeviceTcpAsync",
        patchers.AdbDeviceTcpAsyncFake,
    ):
        yield


@pytest.fixture(autouse=True)
def load_adbkey_fixture() -> Generator[None, str, None]:
    """Patch load_adbkey."""
    with patch(
        "homeassistant.components.androidtv.ADBPythonSync.load_adbkey",
        return_value="signer for testing",
    ):
        yield


@pytest.fixture(autouse=True)
def keygen_fixture() -> Generator[None, Mock, None]:
    """Patch keygen."""
    with patch(
        "homeassistant.components.androidtv.keygen",
        return_value=Mock(),
    ):
        yield

"""Common fixtures for the Midea ccm15 AC Controller tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from ccm15 import CCM15DeviceState, CCM15SlaveDevice
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ccm15.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def ccm15_device() -> Generator[AsyncMock, None, None]:
    """Mock ccm15 device."""
    ccm15_devices = {
        0: CCM15SlaveDevice(bytes.fromhex("000000b0b8001b")),
        1: CCM15SlaveDevice(bytes.fromhex("00000041c0001a")),
    }
    device_state = CCM15DeviceState(devices=ccm15_devices)
    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ):
        yield


@pytest.fixture
def network_failure_ccm15_device() -> Generator[AsyncMock, None, None]:
    """Mock empty set of ccm15 device."""
    device_state = CCM15DeviceState(devices={})
    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ):
        yield

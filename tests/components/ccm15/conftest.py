"""Common fixtures for the Midea ccm15 AC Controller tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from ccm15 import CCM15DeviceState, CCM15SlaveDevice
import pytest

from homeassistant.components.ccm15.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock ccm15 config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 80},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ccm15.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def ccm15_device() -> Generator[AsyncMock]:
    """Mock the ccm15 device status.

    Returns two devices by default. Reconfigure per test via the yielded mock's
    ``return_value`` (e.g. an empty ``CCM15DeviceState``) or ``side_effect``
    (e.g. ``httpx.RequestError`` for an unreachable controller).
    """
    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
    ) as mock_get_status:
        mock_get_status.return_value = CCM15DeviceState(
            devices={
                0: CCM15SlaveDevice(bytes.fromhex("000000b0b8001b")),
                1: CCM15SlaveDevice(bytes.fromhex("00000041c0001a")),
            }
        )
        yield mock_get_status

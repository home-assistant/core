"""Common fixtures for the ADS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ads.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import ADS_CONFIG, MockAdsDevice
from .const import AMS_NET_ID


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the config entry of an ADS connection."""
    return MockConfigEntry(domain=DOMAIN, title=AMS_NET_ID, data=ADS_CONFIG)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up the config entry."""
    with patch(
        "homeassistant.components.ads.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_validate_connection() -> Generator[MagicMock]:
    """Mock the connection probe the config flow runs before creating an entry.

    The probe opens a connection of its own, so leaving it in place would show
    up in every test asserting on the hub's connection.
    """
    with patch(
        "homeassistant.components.ads.config_flow._validate_connection"
    ) as mock_validate:
        yield mock_validate


@pytest.fixture
def mock_create_connection() -> Generator[MagicMock]:
    """Mock the TCP check run before connecting, so the device is reachable."""
    with patch(
        "homeassistant.components.ads.hub.socket.create_connection"
    ) as mock_create_connection:
        yield mock_create_connection


@pytest.fixture
def mock_pyads_connection(
    mock_validate_connection: MagicMock, mock_create_connection: MagicMock
) -> Generator[MagicMock]:
    """Mock the pyads Connection class."""
    with patch("pyads.Connection", autospec=True) as mock_connection:
        yield mock_connection


@pytest.fixture
def mock_ads_device(mock_pyads_connection: MagicMock) -> MockAdsDevice:
    """Route the connection's device notifications to a mock device."""
    device = MockAdsDevice()
    mock_pyads_connection.return_value.add_device_notification.side_effect = (
        device.add_device_notification
    )
    return device


@pytest.fixture
async def setup_ads(hass: HomeAssistant, mock_pyads_connection: MagicMock) -> None:
    """Set up the ADS component against the mocked connection."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: ADS_CONFIG})
    await hass.async_block_till_done()

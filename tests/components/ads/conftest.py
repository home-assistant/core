"""Common fixtures for the ADS tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.ads.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import ADS_CONFIG, MockAdsDevice


@pytest.fixture
def mock_pyads_connection() -> Generator[MagicMock]:
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

"""Common fixtures for the Hue BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hue_ble.const import DOMAIN

from . import TEST_DEVICE_MAC, TEST_DEVICE_NAME

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hue_ble.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_scanner_count() -> Generator[AsyncMock]:
    """Override async_scanner_count."""
    with patch(
        "homeassistant.components.hue_ble.async_scanner_count", return_value=1
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_ble_device() -> Generator[AsyncMock]:
    """Override async_scanner_count."""
    with patch(
        "homeassistant.components.hue_ble.async_ble_device_from_address",
        return_value=generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC),
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None):
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_DEVICE_NAME,
        unique_id=TEST_DEVICE_MAC.lower(),
        data={},
    )


@pytest.fixture
def mock_light() -> Generator[AsyncMock]:
    """Mock a Hue BLE light."""
    with patch(
        "homeassistant.components.hue_ble.HueBleLight", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.address = TEST_DEVICE_MAC
        client.maximum_mireds = 454
        client.minimum_mireds = 153
        client.name = TEST_DEVICE_NAME
        client.manufacturer = "Signify Netherlands B.V."
        client.model = "LTC004"
        client.firmware = "1.104.2"
        client.supports_colour_xy = True
        client.supports_colour_temp = True
        client.supports_brightness = True
        client.supports_on_off = True
        client.available = True
        client.power_state = True
        client.brightness = 100
        client.colour_temp = 250
        client.colour_xy = (0.5, 0.5)
        yield client

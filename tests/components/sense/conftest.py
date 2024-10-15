"""Common methods for SleepIQ."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sense.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    "timeout": 6,
    "email": "test-email",
    "password": "test-password",
    "access_token": "ABC",
    "user_id": "123",
    "monitor_id": "456",
    "device_id": "789",
    "refresh_token": "XYZ",
}

DEVICE_1_NAME = "Car"
DEVICE_1_ID = "abc123"
DEVICE_1_ICON = "car-electric"
DEVICE_1_POWER = 100.0

DEVICE_1_DATA = {
    "name": DEVICE_1_NAME,
    "id": DEVICE_1_ID,
    "icon": "car",
    "tags": {"DeviceListAllowed": "true"},
    "w": DEVICE_1_POWER,
}

DEVICE_2_NAME = "Oven"
DEVICE_2_ID = "def456"
DEVICE_2_ICON = "stove"
DEVICE_2_POWER = 50.0

DEVICE_2_DATA = {
    "name": DEVICE_2_NAME,
    "id": DEVICE_2_ID,
    "icon": "stove",
    "tags": {"DeviceListAllowed": "true"},
    "w": DEVICE_2_POWER,
}
MONITOR_ID = "12345"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sense.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_sense() -> Generator[MagicMock]:
    """Mock an AsyncSleepIQ object with a split foundation."""
    with patch("homeassistant.components.sense.ASyncSenseable", autospec=True) as mock:
        gateway = mock.return_value
        gateway._devices = [DEVICE_1_NAME, DEVICE_2_NAME]
        gateway.sense_monitor_id = MONITOR_ID
        gateway.get_monitor_data.return_value = None
        gateway.get_discovered_device_data.return_value = [DEVICE_1_DATA, DEVICE_2_DATA]
        gateway.update_realtime.return_value = None

        def get_realtime():
            yield {"devices": []}
            yield {"devices": [DEVICE_1_DATA]}
            while True:
                yield {"devices": [DEVICE_1_DATA, DEVICE_2_DATA]}

        gateway.get_realtime.side_effect = get_realtime()

        yield gateway


async def setup_platform(
    hass: HomeAssistant, platform: str | None = None
) -> MockConfigEntry:
    """Set up the Sense platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="test-email",
    )
    mock_entry.add_to_hass(hass)

    if platform:
        with patch("homeassistant.components.sense.PLATFORMS", [platform]):
            assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    return mock_entry

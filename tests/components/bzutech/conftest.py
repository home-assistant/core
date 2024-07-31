"""Define fixtures available for all tests."""

from unittest.mock import AsyncMock, patch

from bzutech.bzutechapi import BzuTech
import pytest

from homeassistant.components.bzutech.const import (
    CONF_CHIPID,
    CONF_ENDPOINT,
    CONF_SENSORPORT,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_EMAIL: "test@email.com",
    CONF_PASSWORD: "test-password",
}

USER_INPUT = {
    CONF_EMAIL: "test@email.com",
    CONF_PASSWORD: "test-password",
    CONF_ENDPOINT: "EP101",
    CONF_CHIPID: "19284",
    CONF_SENSORPORT: "1",
}


@pytest.fixture
def bzutech(hass: HomeAssistant):
    """Mock BzuTech for easier testing."""
    with (
        patch.object(BzuTech, "start", return_value=True),
        patch.object(BzuTech, "get_endpoint_on", return_values="EP101"),
        patch.object(BzuTech, "get_device_names", return_value=["9245", "7564"]),
        patch.object(BzuTech, "get_reading", return_value=27),
        patch("homeassistant.components.bzutech.BzuTech") as mock_bzu,
    ):
        instance = mock_bzu.return_value = BzuTech("test@email.com", "test-password")

        instance.get_endpoint_on.return_value = "EP101"
        instance.get_reading = AsyncMock(return_value=27)
        # instance.get_device_names = MagicMock(return_value=["9465", "25456"])
        # instance.get_sensors = MagicMock(return_value=[])
        # instance.get_sensors_on = MagicMock(return_value=[])
        yield mock_bzu


async def init_integration(
    hass: HomeAssistant,
    *,
    data: dict,
    skip_entry_setup: bool = False,
) -> MockConfigEntry:
    """Set up the bzutech integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry

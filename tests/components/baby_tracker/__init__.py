"""Tests for Baby Tracker (Nighp). Everything here is invented fixture data."""

from datetime import UTC, datetime, timedelta

from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.baby_tracker.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .factories import BABY_ONE_ID, BABY_THREE_ID, BABY_TWO_ID, baby_payload

EMAIL = "parent@example.com"
PASSWORD = "test-password"
EMAIL_TWO = "second-parent@example.com"
ENTRY_ID = "01TESTENTRY0000000000000000"
OWN_DEVICE = "EEEEEEEE-0000-4000-8000-0000000000EE"

BABY_ONE = baby_payload("Baby One", BABY_ONE_ID)
BABY_TWO = baby_payload("Baby Two", BABY_TWO_ID)
BABY_THREE = baby_payload("Baby Three", BABY_THREE_ID)

NOW = datetime(2026, 10, 26, 15, 0, 0, tzinfo=UTC)
DIAPER = "sensor.baby_one_last_diaper"


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Add the entry to Home Assistant and set it up, as core's integration tests do."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def tick(hass: HomeAssistant, minutes: float = 5) -> None:
    """Let the clock reach the next scheduled sync (and a second past it), then settle."""
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(minutes=minutes, seconds=1)
    )
    await hass.async_block_till_done()


def get_baby_device(registry: dr.DeviceRegistry, baby_id: str) -> dr.DeviceEntry | None:
    """Return the device registered for a baby, or None."""
    devices = registry.async_get_devices(identifiers={(DOMAIN, baby_id)})
    return devices[0] if devices else None

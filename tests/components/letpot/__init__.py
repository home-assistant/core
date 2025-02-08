"""Tests for the LetPot integration."""

import datetime

from letpot.models import AuthenticationInfo, LetPotDeviceErrors, LetPotDeviceStatus

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


AUTHENTICATION = AuthenticationInfo(
    access_token="access_token",
    access_token_expires=1738368000,  # 2025-02-01 00:00:00 GMT
    refresh_token="refresh_token",
    refresh_token_expires=1740441600,  # 2025-02-25 00:00:00 GMT
    user_id="a1b2c3d4e5f6a1b2c3d4e5f6",
    email="email@example.com",
)

STATUS = LetPotDeviceStatus(
    errors=LetPotDeviceErrors(low_water=False),
    light_brightness=500,
    light_mode=1,
    light_schedule_end=datetime.time(12, 10),
    light_schedule_start=datetime.time(12, 0),
    online=True,
    plant_days=1,
    pump_mode=1,
    pump_nutrient=None,
    pump_status=0,
    raw=[77, 0, 1, 18, 98, 1, 0, 0, 1, 1, 1, 0, 1, 12, 0, 12, 10, 1, 244, 0, 0, 0],
    system_on=True,
    system_sound=False,
)

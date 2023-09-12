"""Tests for the Freebox sensors."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

from homeassistant.components.freebox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .const import DATA_STORAGE_GET_RAIDS, MOCK_HOST, MOCK_PORT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_raid_array_degraded(hass: HomeAssistant, router: Mock) -> None:
    """Test raid array degraded binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.freebox_server_r2_raid_array_0_degraded").state
        == "off"
    )

    # Now simulate we degraded
    data_storage_get_raids_degraded = deepcopy(DATA_STORAGE_GET_RAIDS)
    data_storage_get_raids_degraded[0]["degraded"] = True
    router().storage.get_raids.return_value = data_storage_get_raids_degraded
    # Simulate an update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    # To execute the save
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.freebox_server_r2_raid_array_0_degraded").state
        == "on"
    )

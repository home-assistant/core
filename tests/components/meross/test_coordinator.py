"""Test Meross Bluetooth coordinator availability."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info

from homeassistant.components.meross.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import MEROSS_MS120_ADDRESS, MEROSS_MS120_SERVICE_INFO


@pytest.mark.usefixtures("mock_bluetooth", "entity_registry_enabled_by_default")
async def test_stale_advertisement_marks_entities_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test the stale timer marks entities unavailable without advertisements."""
    inject_bluetooth_service_info(hass, MEROSS_MS120_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbccddeeff",
        title="Meross MS120",
        data={
            CONF_ADDRESS: MEROSS_MS120_ADDRESS,
            CONF_MODEL: "ms120",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.meross_ms120_temperature")
    assert temp_sensor is not None
    assert temp_sensor.state == "25.0"

    coordinator = entry.runtime_data
    assert coordinator.available
    coordinator._async_advertisement_stale(dt_util.utcnow())
    await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.meross_ms120_temperature")
    assert temp_sensor.state == STATE_UNAVAILABLE

    inject_bluetooth_service_info(hass, MEROSS_MS120_SERVICE_INFO)
    await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.meross_ms120_temperature")
    assert temp_sensor.state == "25.0"

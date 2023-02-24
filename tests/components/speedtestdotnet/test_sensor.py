"""Tests for SpeedTest sensors."""

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.speedtestdotnet import DOMAIN
from homeassistant.components.speedtestdotnet.const import DEFAULT_NAME
from homeassistant.components.speedtestdotnet.sensor import SENSOR_TYPES
from homeassistant.core import HomeAssistant, State

from . import MOCK_PREVIOUS_STATES, MOCK_STATES

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data


async def test_speedtestdotnet_sensors(hass: HomeAssistant) -> None:
    """Test sensors created for speedtestdotnet integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3

    for description in SENSOR_TYPES:
        sensor = hass.states.get(f"sensor.{DEFAULT_NAME}_{description.name}")
        assert sensor
        assert sensor.state == MOCK_STATES[description.key]


async def test_restore_last_state(hass: HomeAssistant) -> None:
    """Test restoring last state for sensors."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(f"sensor.speedtest_{sensor}", sensor_info["state"]),
                {
                    "native_value": sensor_info["native_value"],
                    "native_unit_of_measurement": sensor_info["uom"],
                },
            )
            for sensor, sensor_info in MOCK_PREVIOUS_STATES.items()
        ],
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.pref_disable_polling = True
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3

    for description in SENSOR_TYPES:
        sensor = hass.states.get(f"sensor.speedtest_{description.name}")
        assert sensor
        assert sensor.state == MOCK_PREVIOUS_STATES[description.key]["state"]

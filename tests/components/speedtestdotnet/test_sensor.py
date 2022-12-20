"""Tests for SpeedTest sensors."""
from unittest.mock import MagicMock

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.speedtestdotnet import DOMAIN
from homeassistant.components.speedtestdotnet.const import DEFAULT_NAME
from homeassistant.components.speedtestdotnet.sensor import SENSOR_TYPES
from homeassistant.core import HomeAssistant, State

from . import MOCK_RESULTS, MOCK_SERVERS, MOCK_STATES

from tests.common import MockConfigEntry, mock_restore_cache


async def test_speedtestdotnet_sensors(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test sensors created for speedtestdotnet integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    mock_api.return_value.get_best_server.return_value = MOCK_SERVERS[1][0]
    mock_api.return_value.results.dict.return_value = MOCK_RESULTS

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3

    for description in SENSOR_TYPES:
        sensor = hass.states.get(f"sensor.{DEFAULT_NAME}_{description.name}")
        assert sensor
        assert sensor.state == MOCK_STATES[description.key]


async def test_restore_last_state(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test restoring last state for sensors."""
    mock_restore_cache(
        hass,
        [
            State(f"sensor.speedtest_{sensor}", state)
            for sensor, state in MOCK_STATES.items()
        ],
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3

    for description in SENSOR_TYPES:
        sensor = hass.states.get(f"sensor.speedtest_{description.name}")
        assert sensor
        assert sensor.state == MOCK_STATES[description.key]

"""Tests for SpeedTest sensors."""

from unittest.mock import MagicMock

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.speedtestdotnet.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_RESULTS, MOCK_SERVERS, MOCK_STATES

from tests.common import MockConfigEntry


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

    sensor = hass.states.get("sensor.speedtest_ping")
    assert sensor
    assert sensor.state == MOCK_STATES["ping"]

    sensor = hass.states.get("sensor.speedtest_download")
    assert sensor
    assert sensor.state == MOCK_STATES["download"]

    sensor = hass.states.get("sensor.speedtest_ping")
    assert sensor
    assert sensor.state == MOCK_STATES["ping"]

"""Test pegel_online component."""
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
from aiopegelonline import CurrentMeasurement, Station

from homeassistant.components.pegel_online.const import (
    CONF_STATION,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import utcnow

from . import PegelOnlineMock

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_CONFIG_ENTRY_DATA = {CONF_STATION: "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8"}

MOCK_STATION_DETAILS = Station(
    {
        "uuid": "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
        "number": "501060",
        "shortname": "DRESDEN",
        "longname": "DRESDEN",
        "km": 55.63,
        "agency": "STANDORT DRESDEN",
        "longitude": 13.738831783620384,
        "latitude": 51.054459765598125,
        "water": {"shortname": "ELBE", "longname": "ELBE"},
    }
)
MOCK_STATION_MEASUREMENT = CurrentMeasurement("cm", 56)


async def test_update_error(hass: HomeAssistant) -> None:
    """Tests error during update entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA,
        unique_id=MOCK_CONFIG_ENTRY_DATA[CONF_STATION],
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.pegel_online.PegelOnline") as pegelonline:
        pegelonline.return_value = PegelOnlineMock(
            station_details=MOCK_STATION_DETAILS,
            station_measurement=MOCK_STATION_MEASUREMENT,
        )
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    state = hass.states.get("sensor.dresden_elbe_water_level")
    assert state

    pegelonline().override_side_effect(ClientError)
    async_fire_time_changed(hass, utcnow() + MIN_TIME_BETWEEN_UPDATES)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dresden_elbe_water_level")
    assert state.state == STATE_UNAVAILABLE

"""Test pegel_online component."""
from unittest.mock import patch

from aiopegelonline import CurrentMeasurement, Station

from homeassistant.components.pegel_online.const import CONF_STATION, DOMAIN
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant

from . import _create_mocked_pegelonline

from tests.common import MockConfigEntry

MOCK_CONFIG_ENTRY_DATA = {CONF_STATION: "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8"}

MOCK_STATION_DETAILS = Station(
    "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
    "DRESDEN",
    "STANDORT DRESDEN",
    55.63,
    13.475467710324812,
    51.16440557554545,
    "ELBE",
)
MOCK_STATION_MEASUREMENT = CurrentMeasurement("cm", 56)


async def test_sensor(hass: HomeAssistant) -> None:
    """Tests sensor entity."""
    mocked_pegelonline = _create_mocked_pegelonline(
        station_details=MOCK_STATION_DETAILS,
        station_measurement=MOCK_STATION_MEASUREMENT,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA,
        unique_id=MOCK_CONFIG_ENTRY_DATA[CONF_STATION],
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.pegel_online.PegelOnline",
        return_value=mocked_pegelonline,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    state = hass.states.get("sensor.dresden_elbe_water_level")
    assert state.name == "DRESDEN ELBE Water level"
    assert state.state == "56"
    assert state.attributes[ATTR_LATITUDE] == 51.16440557554545
    assert state.attributes[ATTR_LONGITUDE] == 13.475467710324812

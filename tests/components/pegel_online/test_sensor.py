"""Test pegel_online component."""

from unittest.mock import patch

from aiopegelonline.models import Station, StationMeasurements
import pytest

from homeassistant.components.pegel_online.const import CONF_STATION, DOMAIN
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import PegelOnlineMock
from .const import (
    MOCK_CONFIG_ENTRY_DATA_DRESDEN,
    MOCK_CONFIG_ENTRY_DATA_HANAU_BRIDGE,
    MOCK_CONFIG_ENTRY_DATA_WUERZBURG,
    MOCK_STATION_DETAILS_DRESDEN,
    MOCK_STATION_DETAILS_HANAU_BRIDGE,
    MOCK_STATION_DETAILS_WUERZBURG,
    MOCK_STATION_MEASUREMENT_DRESDEN,
    MOCK_STATION_MEASUREMENT_HANAU_BRIDGE,
    MOCK_STATION_MEASUREMENT_WUERZBURG,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    (
        "mock_config_entry_data",
        "mock_station_details",
        "mock_station_measurement",
        "expected_states",
    ),
    [
        (
            MOCK_CONFIG_ENTRY_DATA_DRESDEN,
            MOCK_STATION_DETAILS_DRESDEN,
            MOCK_STATION_MEASUREMENT_DRESDEN,
            {
                "sensor.dresden_elbe_water_volume_flow": (
                    "DRESDEN ELBE Water volume flow",
                    "88.4",
                    "m³/s",
                ),
                "sensor.dresden_elbe_water_level": (
                    "DRESDEN ELBE Water level",
                    "62",
                    "cm",
                ),
            },
        ),
        (
            MOCK_CONFIG_ENTRY_DATA_HANAU_BRIDGE,
            MOCK_STATION_DETAILS_HANAU_BRIDGE,
            MOCK_STATION_MEASUREMENT_HANAU_BRIDGE,
            {
                "sensor.hanau_brucke_dfh_main_clearance_height": (
                    "HANAU BRÜCKE DFH MAIN Clearance height",
                    "715",
                    "cm",
                ),
            },
        ),
        (
            MOCK_CONFIG_ENTRY_DATA_WUERZBURG,
            MOCK_STATION_DETAILS_WUERZBURG,
            MOCK_STATION_MEASUREMENT_WUERZBURG,
            {
                "sensor.wurzburg_main_air_temperature": (
                    "WÜRZBURG MAIN Air temperature",
                    "21.2",
                    "°C",
                ),
                "sensor.wurzburg_main_oxygen_level": (
                    "WÜRZBURG MAIN Oxygen level",
                    "8.4",
                    "mg/l",
                ),
                "sensor.wurzburg_main_ph": (
                    "WÜRZBURG MAIN pH",
                    "8.1",
                    None,
                ),
                "sensor.wurzburg_main_water_flow_speed": (
                    "WÜRZBURG MAIN Water flow speed",
                    "0.58",
                    "m/s",
                ),
                "sensor.wurzburg_main_water_volume_flow": (
                    "WÜRZBURG MAIN Water volume flow",
                    "102",
                    "m³/s",
                ),
                "sensor.wurzburg_main_water_level": (
                    "WÜRZBURG MAIN Water level",
                    "159",
                    "cm",
                ),
                "sensor.wurzburg_main_water_temperature": (
                    "WÜRZBURG MAIN Water temperature",
                    "22.1",
                    "°C",
                ),
            },
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry_data: dict,
    mock_station_details: Station,
    mock_station_measurement: StationMeasurements,
    expected_states: dict,
    entity_registry_enabled_by_default: None,
) -> None:
    """Tests sensor entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data,
        unique_id=mock_config_entry_data[CONF_STATION],
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.pegel_online.PegelOnline") as pegelonline:
        pegelonline.return_value = PegelOnlineMock(
            station_details=mock_station_details,
            station_measurements=mock_station_measurement,
        )
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == len(expected_states)

    for state_name, state_data in expected_states.items():
        state = hass.states.get(state_name)
        assert state.name == state_data[0]
        assert state.state == state_data[1]
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == state_data[2]
        if mock_station_details.latitude is not None:
            assert state.attributes[ATTR_LATITUDE] == mock_station_details.latitude
            assert state.attributes[ATTR_LONGITUDE] == mock_station_details.longitude

"""Tests for the IMGW-PIB integration."""

from datetime import UTC, datetime
from unittest.mock import PropertyMock, patch

from imgw_pib import HydrologicalData, SensorData

from homeassistant.components.imgw_pib.const import DOMAIN

from tests.common import MockConfigEntry

HYDROLOGICAL_STATIONS = {"123": "River Name (Station Name)"}
HYDROLOGICAL_DATA = HydrologicalData(
    station="Station Name",
    river="River Name",
    station_id="123",
    water_level=SensorData(name="Water Level", value=526.0),
    flood_alarm_level=SensorData(name="Flood Alarm Level", value=630.0),
    flood_warning_level=SensorData(name="Flood Warning Level", value=590.0),
    water_temperature=SensorData(name="Water Temperature", value=10.8),
    flood_alarm=False,
    flood_warning=False,
    water_level_measurement_date=datetime(2024, 4, 27, 10, 0, tzinfo=UTC),
    water_temperature_measurement_date=datetime(2024, 4, 27, 10, 10, tzinfo=UTC),
)


async def init_integration(hass) -> MockConfigEntry:
    """Set up the IMGW-PIB integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="River Name (Station Name)",
        unique_id="123",
        data={
            "station_id": "123",
        },
    )

    with (
        patch("homeassistant.components.imgw_pib.ImgwPib.update_hydrological_stations"),
        patch("homeassistant.components.imgw_pib.ImgwPib._update_hydrological_details"),
        patch(
            "homeassistant.components.imgw_pib.ImgwPib.get_hydrological_data",
            return_value=HYDROLOGICAL_DATA,
        ),
        patch(
            "homeassistant.components.imgw_pib.ImgwPib.hydrological_stations",
            new_callable=PropertyMock,
            return_value=HYDROLOGICAL_STATIONS,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry

"""Tests for the Nettigo Air Monitor integration."""
from unittest.mock import patch

from homeassistant.components.nam.const import DOMAIN

from tests.common import MockConfigEntry

INCOMPLETE_NAM_DATA = {
    "software_version": "NAMF-2020-36",
    "sensordatavalues": [],
}

NAM_DATA = {
    "software_version": "NAMF-2020-36",
    "sensordatavalues": [
        {"value_type": "SDS_P1", "value": "18.65"},
        {"value_type": "SDS_P2", "value": "11.03"},
        {"value_type": "SPS30_P0", "value": "31.23"},
        {"value_type": "SPS30_P1", "value": "21.23"},
        {"value_type": "SPS30_P2", "value": "34.32"},
        {"value_type": "SPS30_P4", "value": "24.72"},
        {"value_type": "conc_co2_ppm", "value": "865"},
        {"value_type": "BME280_temperature", "value": "7.56"},
        {"value_type": "BME280_humidity", "value": "45.69"},
        {"value_type": "BME280_pressure", "value": "101101.17"},
        {"value_type": "BMP280_temperature", "value": "5.56"},
        {"value_type": "BMP280_pressure", "value": "102201.18"},
        {"value_type": "SHT3X_temperature", "value": "6.28"},
        {"value_type": "SHT3X_humidity", "value": "34.69"},
        {"value_type": "humidity", "value": "46.23"},
        {"value_type": "temperature", "value": "6.26"},
        {"value_type": "HECA_temperature", "value": "7.95"},
        {"value_type": "HECA_humidity", "value": "49.97"},
        {"value_type": "signal", "value": "-72"},
    ],
}


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Nettigo Air Monitor integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="10.10.2.3",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"host": "10.10.2.3"},
    )

    with patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_get_data",
        return_value=NAM_DATA,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry

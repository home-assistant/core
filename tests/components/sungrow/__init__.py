"""Tests for the Sungrow Solar Energy integration."""
from homeassistant.components.sungrow import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "port": 502,
        },
    )
    entry.add_to_hass(hass)
    return entry


inverter_data = {
    "4990 ~ 4999 - Serial number": b"A1234567890",
    "5001 - Nominal active power": 5.0,
    "5003 - Daily power yields": 20.7,
    "5004 - Total power yields": 161,
    "5006 - Total running time": 166,
    "5008 - Internal temperature": 39.0,
    "5009 - Total apparent power": 2940,
    "5011 - MPPT 1 voltage": 470.6,
    "5012 - MPPT 1 current": 3.2,
    "5013 - MPPT 2 voltage": 523.9,
    "5014 - MPPT 2 current": 3.1,
    "5015 - MPPT 3 voltage": 0.0,
    "5016 - MPPT 3 current": 0.0,
    "5017 - Total DC power": 3082,
    "5019 - Phase A voltage": 232.8,
    "5020 - Phase B voltage": 232.0,
    "5021 - Phase C voltage": 236.7,
    "5022 - Phase A current": 4.1,
    "5023 - Phase B current": 4.1,
    "5024 - Phase C current": 4.1,
    "5031 - Total active power": 2940,
    "5033 - Total reactive power": 6,
    "5035 - Power factor": 1000,
    "5036 - Grid frequency": 49.9,
    "5049 - Nominal reactive power": 2.5,
    "5083 - Meter power": 0,
    "5085 - Meter A phase power": 0,
    "5087 - Meter B phase power": 0,
    "5089 - Meter C phase power": 0,
    "5097 - Daily import energy": 0.0,
    "5113 - Daily running time": 634,
    "5144 - Total power yields": 161.0,
    "5146 - Negative voltage to ground": 0.0,
    "5148 - Grid frequency": 49.95,
}

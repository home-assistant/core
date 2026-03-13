"""Tests for the Solarwatt integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_USER_INPUT: dict[str, object] = {
    CONF_HOST: "batteryflex.local",
    CONF_PORT: 8080,
}

# minimal example payload of /all for our tests
MOCK_PAYLOAD: dict[str, object] = {
    "ID": {
        "SN": "0004A20B000BF3A3",
        "DC": 1,
        "PV": "1.10.1",
    },
    "S": {
        "AC": {
            "ACV": 230.1,
            "ACI": 1.23,  # codespell:ignore
            "ACF": 49.98,
        },
        "B": {
            "SOC": 42,
            "SOH": 95.0,
            "BV": 109.7,
            "BI": 3.9,
            "COUT": 123.4,
            "CIN": 567.8,
            "EOUT": 1111,
            "EIN": 2222,
        },
        "DC": {
            "DCV": 418,
            "DCPC": 3293,
            "DCPD": 3293,
            "TAMB": 28,
        },
    },
    "H": {
        "HP": 424.3,
    },
    "N": {
        "NP": -1,
        "NF": 49.98,
        "NV": 231,
    },
    "A": {
        "VSYS": 18580,
        "VBKP": 2595,
    },
    "C": {
        "V": "6.13.413",
    },
    "P": {
        "IP": "192.168.178.85",
    },
}


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Solarwatt integration for tests."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

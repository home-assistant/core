"""Tests for the sma integration."""
from unittest.mock import patch

from homeassistant.components.sma.const import DOMAIN
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MOCK_DEVICE = {
    "manufacturer": "SMA",
    "name": "SMA Device Name",
    "type": "Sunny Boy 3.6",
    "serial": "123456789",
}

MOCK_USER_INPUT = {
    "host": "1.1.1.1",
    "ssl": True,
    "verify_ssl": False,
    "group": "user",
    "password": "password",
}

MOCK_IMPORT = {
    "platform": "sma",
    "host": "1.1.1.1",
    "ssl": True,
    "verify_ssl": False,
    "group": "user",
    "password": "password",
    "sensors": ["pv_power", "daily_yield", "total_yield", "not_existing_sensors"],
    "custom": {
        "yesterday_consumption": {
            "factor": 1000.0,
            "key": "6400_00543A01",
            "unit": "kWh",
        }
    },
}

MOCK_CUSTOM_SENSOR = {
    "name": "yesterday_consumption",
    "key": "6400_00543A01",
    "unit": "kWh",
    "factor": 1000,
}

MOCK_CUSTOM_SENSOR2 = {
    "name": "device_type_id",
    "key": "6800_08822000",
    "unit": "",
    "path": '"1"[0].val[0].tag',
}

MOCK_SETUP_DATA = dict(
    {
        "custom": {},
        "device_info": MOCK_DEVICE,
        "sensors": [],
    },
    **MOCK_USER_INPUT,
)

MOCK_CUSTOM_SETUP_DATA = dict(
    {
        "custom": {
            MOCK_CUSTOM_SENSOR["name"]: {
                "factor": MOCK_CUSTOM_SENSOR["factor"],
                "key": MOCK_CUSTOM_SENSOR["key"],
                "path": None,
                "unit": MOCK_CUSTOM_SENSOR["unit"],
            },
            MOCK_CUSTOM_SENSOR2["name"]: {
                "factor": 1.0,
                "key": MOCK_CUSTOM_SENSOR2["key"],
                "path": MOCK_CUSTOM_SENSOR2["path"],
                "unit": MOCK_CUSTOM_SENSOR2["unit"],
            },
        },
        "device_info": MOCK_DEVICE,
        "sensors": [],
    },
    **MOCK_USER_INPUT,
)

MOCK_LEGACY_ENTRY = er.RegistryEntry(
    entity_id="sensor.pv_power",
    unique_id="sma-6100_0046C200-pv_power",
    platform="sma",
    unit_of_measurement="W",
    original_name="pv_power",
)


async def init_integration(hass):
    """Create a fake SMA Config Entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE["name"],
        unique_id=MOCK_DEVICE["serial"],
        data=MOCK_CUSTOM_SETUP_DATA,
        source="import",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_config_entry_first_refresh"
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _patch_validate_input(return_value=MOCK_DEVICE, side_effect=None):
    return patch(
        "homeassistant.components.sma.config_flow.validate_input",
        return_value=return_value,
        side_effect=side_effect,
    )


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.sma.async_setup_entry",
        return_value=return_value,
    )

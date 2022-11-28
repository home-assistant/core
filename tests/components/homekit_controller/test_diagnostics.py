"""Test homekit_controller diagnostics."""
from aiohttp import ClientSession

from homeassistant.components.homekit_controller.const import KNOWN_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.components.homekit_controller.common import (
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_config_entry(hass: HomeAssistant, hass_client: ClientSession, utcnow):
    """Test generating diagnostics for a config entry."""
    accessories = await setup_accessories_from_file(hass, "koogeek_ls1.json")
    config_entry, _ = await setup_test_accessories(hass, accessories)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag == {
        "config-entry": {
            "title": "test",
            "version": 1,
            "data": {"AccessoryPairingID": "00:00:00:00:00:00"},
        },
        "config-num": 0,
        "entity-map": [
            {
                "aid": 1,
                "services": [
                    {
                        "iid": 1,
                        "type": "0000003E-0000-1000-8000-0026BB765291",
                        "characteristics": [
                            {
                                "type": "00000023-0000-1000-8000-0026BB765291",
                                "iid": 2,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "Koogeek-LS1-20833F",
                                "description": "Name",
                                "maxLen": 64,
                            },
                            {
                                "type": "00000020-0000-1000-8000-0026BB765291",
                                "iid": 3,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "Koogeek",
                                "description": "Manufacturer",
                                "maxLen": 64,
                            },
                            {
                                "type": "00000021-0000-1000-8000-0026BB765291",
                                "iid": 4,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "LS1",
                                "description": "Model",
                                "maxLen": 64,
                            },
                            {
                                "type": "00000030-0000-1000-8000-0026BB765291",
                                "iid": 5,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "**REDACTED**",
                                "description": "Serial Number",
                                "maxLen": 64,
                            },
                            {
                                "type": "00000014-0000-1000-8000-0026BB765291",
                                "iid": 6,
                                "perms": ["pw"],
                                "format": "bool",
                                "description": "Identify",
                            },
                            {
                                "type": "00000052-0000-1000-8000-0026BB765291",
                                "iid": 23,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "2.2.15",
                                "description": "Firmware Revision",
                                "maxLen": 64,
                            },
                        ],
                    },
                    {
                        "iid": 7,
                        "type": "00000043-0000-1000-8000-0026BB765291",
                        "characteristics": [
                            {
                                "type": "00000025-0000-1000-8000-0026BB765291",
                                "iid": 8,
                                "perms": ["pr", "pw", "ev"],
                                "format": "bool",
                                "value": False,
                                "description": "On",
                            },
                            {
                                "type": "00000013-0000-1000-8000-0026BB765291",
                                "iid": 9,
                                "perms": ["pr", "pw", "ev"],
                                "format": "float",
                                "value": 44,
                                "description": "Hue",
                                "unit": "arcdegrees",
                                "minValue": 0,
                                "maxValue": 359,
                                "minStep": 1,
                            },
                            {
                                "type": "0000002F-0000-1000-8000-0026BB765291",
                                "iid": 10,
                                "perms": ["pr", "pw", "ev"],
                                "format": "float",
                                "value": 0,
                                "description": "Saturation",
                                "unit": "percentage",
                                "minValue": 0,
                                "maxValue": 100,
                                "minStep": 1,
                            },
                            {
                                "type": "00000008-0000-1000-8000-0026BB765291",
                                "iid": 11,
                                "perms": ["pr", "pw", "ev"],
                                "format": "int",
                                "value": 100,
                                "description": "Brightness",
                                "unit": "percentage",
                                "minValue": 0,
                                "maxValue": 100,
                                "minStep": 1,
                            },
                            {
                                "type": "00000023-0000-1000-8000-0026BB765291",
                                "iid": 12,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "Light Strip",
                                "description": "Name",
                                "maxLen": 64,
                            },
                        ],
                    },
                    {
                        "iid": 13,
                        "type": "4AAAF940-0DEC-11E5-B939-0800200C9A66",
                        "characteristics": [
                            {
                                "type": "4AAAF942-0DEC-11E5-B939-0800200C9A66",
                                "iid": 14,
                                "perms": ["pr", "pw"],
                                "format": "tlv8",
                                "value": "AHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                                "description": "TIMER_SETTINGS",
                            }
                        ],
                    },
                    {
                        "iid": 15,
                        "type": "151909D0-3802-11E4-916C-0800200C9A66",
                        "characteristics": [
                            {
                                "type": "151909D2-3802-11E4-916C-0800200C9A66",
                                "iid": 16,
                                "perms": ["pr", "hd"],
                                "format": "string",
                                "value": "url,data",
                                "description": "FW Upgrade supported types",
                                "maxLen": 64,
                            },
                            {
                                "type": "151909D1-3802-11E4-916C-0800200C9A66",
                                "iid": 17,
                                "perms": ["pw", "hd"],
                                "format": "string",
                                "description": "FW Upgrade URL",
                                "maxLen": 64,
                            },
                            {
                                "type": "151909D6-3802-11E4-916C-0800200C9A66",
                                "iid": 18,
                                "perms": ["pr", "ev", "hd"],
                                "format": "int",
                                "value": 0,
                                "description": "FW Upgrade Status",
                            },
                            {
                                "type": "151909D7-3802-11E4-916C-0800200C9A66",
                                "iid": 19,
                                "perms": ["pw", "hd"],
                                "format": "data",
                                "description": "FW Upgrade Data",
                            },
                        ],
                    },
                    {
                        "iid": 20,
                        "type": "151909D3-3802-11E4-916C-0800200C9A66",
                        "characteristics": [
                            {
                                "type": "151909D5-3802-11E4-916C-0800200C9A66",
                                "iid": 21,
                                "perms": ["pr", "pw"],
                                "format": "int",
                                "value": 0,
                                "description": "Timezone",
                            },
                            {
                                "type": "151909D4-3802-11E4-916C-0800200C9A66",
                                "iid": 22,
                                "perms": ["pr", "pw"],
                                "format": "int",
                                "value": 1550348623,
                                "description": "Time value since Epoch",
                            },
                        ],
                    },
                ],
            }
        ],
        "devices": [
            {
                "name": "Koogeek-LS1-20833F",
                "model": "LS1",
                "manfacturer": "Koogeek",
                "sw_version": "2.2.15",
                "hw_version": "",
                "entities": [
                    {
                        "device_class": None,
                        "disabled": False,
                        "disabled_by": None,
                        "entity_category": "diagnostic",
                        "icon": None,
                        "original_device_class": None,
                        "original_icon": None,
                        "original_name": "Koogeek-LS1-20833F Identify",
                        "state": {
                            "attributes": {
                                "friendly_name": "Koogeek-LS1-20833F Identify"
                            },
                            "entity_id": "button.koogeek_ls1_20833f_identify",
                            "last_changed": "2023-01-01T00:00:00+00:00",
                            "last_updated": "2023-01-01T00:00:00+00:00",
                            "state": "unknown",
                        },
                        "unit_of_measurement": None,
                    },
                    {
                        "device_class": None,
                        "disabled": False,
                        "disabled_by": None,
                        "entity_category": None,
                        "icon": None,
                        "original_device_class": None,
                        "original_icon": None,
                        "original_name": "Koogeek-LS1-20833F Light Strip",
                        "state": {
                            "attributes": {
                                "friendly_name": "Koogeek-LS1-20833F Light Strip",
                                "supported_color_modes": ["hs"],
                                "supported_features": 0,
                            },
                            "entity_id": "light.koogeek_ls1_20833f_light_strip",
                            "last_changed": "2023-01-01T00:00:00+00:00",
                            "last_updated": "2023-01-01T00:00:00+00:00",
                            "state": "off",
                        },
                        "unit_of_measurement": None,
                    },
                ],
            }
        ],
    }


async def test_device(hass: HomeAssistant, hass_client: ClientSession, utcnow):
    """Test generating diagnostics for a device entry."""
    accessories = await setup_accessories_from_file(hass, "koogeek_ls1.json")
    config_entry, _ = await setup_test_accessories(hass, accessories)

    connection = hass.data[KNOWN_DEVICES]["00:00:00:00:00:00"]
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(connection.devices[1])

    diag = await get_diagnostics_for_device(hass, hass_client, config_entry, device)

    assert diag == {
        "config-entry": {
            "title": "test",
            "version": 1,
            "data": {"AccessoryPairingID": "00:00:00:00:00:00"},
        },
        "config-num": 0,
        "entity-map": [
            {
                "aid": 1,
                "services": [
                    {
                        "iid": 1,
                        "type": "0000003E-0000-1000-8000-0026BB765291",
                        "characteristics": [
                            {
                                "type": "00000023-0000-1000-8000-0026BB765291",
                                "iid": 2,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "Koogeek-LS1-20833F",
                                "description": "Name",
                                "maxLen": 64,
                            },
                            {
                                "type": "00000020-0000-1000-8000-0026BB765291",
                                "iid": 3,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "Koogeek",
                                "description": "Manufacturer",
                                "maxLen": 64,
                            },
                            {
                                "type": "00000021-0000-1000-8000-0026BB765291",
                                "iid": 4,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "LS1",
                                "description": "Model",
                                "maxLen": 64,
                            },
                            {
                                "type": "00000030-0000-1000-8000-0026BB765291",
                                "iid": 5,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "**REDACTED**",
                                "description": "Serial Number",
                                "maxLen": 64,
                            },
                            {
                                "type": "00000014-0000-1000-8000-0026BB765291",
                                "iid": 6,
                                "perms": ["pw"],
                                "format": "bool",
                                "description": "Identify",
                            },
                            {
                                "type": "00000052-0000-1000-8000-0026BB765291",
                                "iid": 23,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "2.2.15",
                                "description": "Firmware Revision",
                                "maxLen": 64,
                            },
                        ],
                    },
                    {
                        "iid": 7,
                        "type": "00000043-0000-1000-8000-0026BB765291",
                        "characteristics": [
                            {
                                "type": "00000025-0000-1000-8000-0026BB765291",
                                "iid": 8,
                                "perms": ["pr", "pw", "ev"],
                                "format": "bool",
                                "value": False,
                                "description": "On",
                            },
                            {
                                "type": "00000013-0000-1000-8000-0026BB765291",
                                "iid": 9,
                                "perms": ["pr", "pw", "ev"],
                                "format": "float",
                                "value": 44,
                                "description": "Hue",
                                "unit": "arcdegrees",
                                "minValue": 0,
                                "maxValue": 359,
                                "minStep": 1,
                            },
                            {
                                "type": "0000002F-0000-1000-8000-0026BB765291",
                                "iid": 10,
                                "perms": ["pr", "pw", "ev"],
                                "format": "float",
                                "value": 0,
                                "description": "Saturation",
                                "unit": "percentage",
                                "minValue": 0,
                                "maxValue": 100,
                                "minStep": 1,
                            },
                            {
                                "type": "00000008-0000-1000-8000-0026BB765291",
                                "iid": 11,
                                "perms": ["pr", "pw", "ev"],
                                "format": "int",
                                "value": 100,
                                "description": "Brightness",
                                "unit": "percentage",
                                "minValue": 0,
                                "maxValue": 100,
                                "minStep": 1,
                            },
                            {
                                "type": "00000023-0000-1000-8000-0026BB765291",
                                "iid": 12,
                                "perms": ["pr"],
                                "format": "string",
                                "value": "Light Strip",
                                "description": "Name",
                                "maxLen": 64,
                            },
                        ],
                    },
                    {
                        "iid": 13,
                        "type": "4AAAF940-0DEC-11E5-B939-0800200C9A66",
                        "characteristics": [
                            {
                                "type": "4AAAF942-0DEC-11E5-B939-0800200C9A66",
                                "iid": 14,
                                "perms": ["pr", "pw"],
                                "format": "tlv8",
                                "value": "AHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                                "description": "TIMER_SETTINGS",
                            }
                        ],
                    },
                    {
                        "iid": 15,
                        "type": "151909D0-3802-11E4-916C-0800200C9A66",
                        "characteristics": [
                            {
                                "type": "151909D2-3802-11E4-916C-0800200C9A66",
                                "iid": 16,
                                "perms": ["pr", "hd"],
                                "format": "string",
                                "value": "url,data",
                                "description": "FW Upgrade supported types",
                                "maxLen": 64,
                            },
                            {
                                "type": "151909D1-3802-11E4-916C-0800200C9A66",
                                "iid": 17,
                                "perms": ["pw", "hd"],
                                "format": "string",
                                "description": "FW Upgrade URL",
                                "maxLen": 64,
                            },
                            {
                                "type": "151909D6-3802-11E4-916C-0800200C9A66",
                                "iid": 18,
                                "perms": ["pr", "ev", "hd"],
                                "format": "int",
                                "value": 0,
                                "description": "FW Upgrade Status",
                            },
                            {
                                "type": "151909D7-3802-11E4-916C-0800200C9A66",
                                "iid": 19,
                                "perms": ["pw", "hd"],
                                "format": "data",
                                "description": "FW Upgrade Data",
                            },
                        ],
                    },
                    {
                        "iid": 20,
                        "type": "151909D3-3802-11E4-916C-0800200C9A66",
                        "characteristics": [
                            {
                                "type": "151909D5-3802-11E4-916C-0800200C9A66",
                                "iid": 21,
                                "perms": ["pr", "pw"],
                                "format": "int",
                                "value": 0,
                                "description": "Timezone",
                            },
                            {
                                "type": "151909D4-3802-11E4-916C-0800200C9A66",
                                "iid": 22,
                                "perms": ["pr", "pw"],
                                "format": "int",
                                "value": 1550348623,
                                "description": "Time value since Epoch",
                            },
                        ],
                    },
                ],
            }
        ],
        "device": {
            "name": "Koogeek-LS1-20833F",
            "model": "LS1",
            "manfacturer": "Koogeek",
            "sw_version": "2.2.15",
            "hw_version": "",
            "entities": [
                {
                    "device_class": None,
                    "disabled": False,
                    "disabled_by": None,
                    "entity_category": "diagnostic",
                    "icon": None,
                    "original_device_class": None,
                    "original_icon": None,
                    "original_name": "Koogeek-LS1-20833F Identify",
                    "state": {
                        "attributes": {
                            "friendly_name": "Koogeek-LS1-20833F " "Identify"
                        },
                        "entity_id": "button.koogeek_ls1_20833f_identify",
                        "last_changed": "2023-01-01T00:00:00+00:00",
                        "last_updated": "2023-01-01T00:00:00+00:00",
                        "state": "unknown",
                    },
                    "unit_of_measurement": None,
                },
                {
                    "device_class": None,
                    "disabled": False,
                    "disabled_by": None,
                    "entity_category": None,
                    "icon": None,
                    "original_device_class": None,
                    "original_icon": None,
                    "original_name": "Koogeek-LS1-20833F Light Strip",
                    "state": {
                        "attributes": {
                            "friendly_name": "Koogeek-LS1-20833F Light Strip",
                            "supported_color_modes": ["hs"],
                            "supported_features": 0,
                        },
                        "entity_id": "light.koogeek_ls1_20833f_light_strip",
                        "last_changed": "2023-01-01T00:00:00+00:00",
                        "last_updated": "2023-01-01T00:00:00+00:00",
                        "state": "off",
                    },
                    "unit_of_measurement": None,
                },
            ],
        },
    }

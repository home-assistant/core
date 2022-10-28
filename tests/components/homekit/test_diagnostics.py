"""Test homekit diagnostics."""
from unittest.mock import ANY, patch

from homeassistant.components.homekit.const import (
    CONF_HOMEKIT_MODE,
    DOMAIN,
    HOMEKIT_MODE_ACCESSORY,
)
from homeassistant.const import CONF_NAME, CONF_PORT, EVENT_HOMEASSISTANT_STARTED

from .util import async_init_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_config_entry_not_running(
    hass, hass_client, hk_driver, mock_async_zeroconf
):
    """Test generating diagnostics for a config entry."""
    entry = await async_init_integration(hass)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == {
        "config-entry": {
            "data": {"name": "mock_name", "port": 12345},
            "options": {},
            "title": "Mock Title",
            "version": 1,
        },
        "status": 0,
    }


async def test_config_entry_running(hass, hass_client, hk_driver, mock_async_zeroconf):
    """Test generating diagnostics for a bridge config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == {
        "bridge": {},
        "accessories": [
            {
                "aid": 1,
                "services": [
                    {
                        "characteristics": [
                            {"format": "bool", "iid": 2, "perms": ["pw"], "type": "14"},
                            {
                                "format": "string",
                                "iid": 3,
                                "perms": ["pr"],
                                "type": "20",
                                "value": "Home Assistant",
                            },
                            {
                                "format": "string",
                                "iid": 4,
                                "perms": ["pr"],
                                "type": "21",
                                "value": "Bridge",
                            },
                            {
                                "format": "string",
                                "iid": 5,
                                "perms": ["pr"],
                                "type": "23",
                                "value": "mock_name",
                            },
                            {
                                "format": "string",
                                "iid": 6,
                                "perms": ["pr"],
                                "type": "30",
                                "value": "homekit.bridge",
                            },
                            {
                                "format": "string",
                                "iid": 7,
                                "perms": ["pr"],
                                "type": "52",
                                "value": ANY,
                            },
                        ],
                        "iid": 1,
                        "type": "3E",
                    },
                    {
                        "characteristics": [
                            {
                                "format": "string",
                                "iid": 9,
                                "perms": ["pr", "ev"],
                                "type": "37",
                                "value": "01.01.00",
                            }
                        ],
                        "iid": 8,
                        "type": "A2",
                    },
                ],
            }
        ],
        "client_properties": {},
        "config-entry": {
            "data": {"name": "mock_name", "port": 12345},
            "options": {},
            "title": "Mock Title",
            "version": 1,
        },
        "config_version": 2,
        "pairing_id": ANY,
        "status": 1,
    }

    with patch("pyhap.accessory_driver.AccessoryDriver.async_start"), patch(
        "homeassistant.components.homekit.HomeKit.async_stop"
    ), patch("homeassistant.components.homekit.async_port_is_available"):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_config_entry_accessory(
    hass, hass_client, hk_driver, mock_async_zeroconf
):
    """Test generating diagnostics for an accessory config entry."""
    hass.states.async_set("light.demo", "on")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "mock_name",
            CONF_PORT: 12345,
            CONF_HOMEKIT_MODE: HOMEKIT_MODE_ACCESSORY,
            "filter": {
                "exclude_domains": [],
                "exclude_entities": [],
                "include_domains": [],
                "include_entities": ["light.demo"],
            },
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == {
        "accessories": [
            {
                "aid": 1,
                "services": [
                    {
                        "characteristics": [
                            {"format": "bool", "iid": 2, "perms": ["pw"], "type": "14"},
                            {
                                "format": "string",
                                "iid": 3,
                                "perms": ["pr"],
                                "type": "20",
                                "value": "Home Assistant " "Light",
                            },
                            {
                                "format": "string",
                                "iid": 4,
                                "perms": ["pr"],
                                "type": "21",
                                "value": "Light",
                            },
                            {
                                "format": "string",
                                "iid": 5,
                                "perms": ["pr"],
                                "type": "23",
                                "value": "demo",
                            },
                            {
                                "format": "string",
                                "iid": 6,
                                "perms": ["pr"],
                                "type": "30",
                                "value": "light.demo",
                            },
                            {
                                "format": "string",
                                "iid": 7,
                                "perms": ["pr"],
                                "type": "52",
                                "value": ANY,
                            },
                        ],
                        "iid": 1,
                        "type": "3E",
                    },
                    {
                        "characteristics": [
                            {
                                "format": "string",
                                "iid": 9,
                                "perms": ["pr", "ev"],
                                "type": "37",
                                "value": "01.01.00",
                            }
                        ],
                        "iid": 8,
                        "type": "A2",
                    },
                    {
                        "characteristics": [
                            {
                                "format": "bool",
                                "iid": 11,
                                "perms": ["pr", "pw", "ev"],
                                "type": "25",
                                "value": True,
                            }
                        ],
                        "iid": 10,
                        "type": "43",
                    },
                ],
            }
        ],
        "accessory": {
            "aid": 1,
            "category": 5,
            "config": {},
            "entity_id": "light.demo",
            "entity_state": {
                "attributes": {},
                "context": {"id": ANY, "parent_id": None, "user_id": None},
                "entity_id": "light.demo",
                "last_changed": ANY,
                "last_updated": ANY,
                "state": "on",
            },
            "name": "demo",
        },
        "client_properties": {},
        "config-entry": {
            "data": {"name": "mock_name", "port": 12345},
            "options": {
                "filter": {
                    "exclude_domains": [],
                    "exclude_entities": [],
                    "include_domains": [],
                    "include_entities": ["light.demo"],
                },
                "mode": "accessory",
            },
            "title": "Mock Title",
            "version": 1,
        },
        "config_version": 2,
        "pairing_id": ANY,
        "status": 1,
    }
    with patch("pyhap.accessory_driver.AccessoryDriver.async_start"), patch(
        "homeassistant.components.homekit.HomeKit.async_stop"
    ), patch("homeassistant.components.homekit.async_port_is_available"):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

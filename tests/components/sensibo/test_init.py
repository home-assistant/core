"""Test for Sensibo component Init."""
from __future__ import annotations

from unittest.mock import patch

from pysensibo.model import SensiboData

from homeassistant import config_entries
from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.components.sensibo.util import NoUsernameError
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_setup_entry(hass: HomeAssistant, get_data: SensiboData) -> None:
    """Test setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="12",
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.LOADED


async def test_migrate_entry(hass: HomeAssistant, get_data: SensiboData) -> None:
    """Test migrate entry unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="12",
        version=1,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.unique_id == "username"


async def test_migrate_entry_fails(hass: HomeAssistant, get_data: SensiboData) -> None:
    """Test migrate entry unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="12",
        version=1,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        side_effect=NoUsernameError("No username returned"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 1
    assert entry.unique_id == "12"


async def test_unload_entry(hass: HomeAssistant, get_data: SensiboData) -> None:
    """Test unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="12",
        version="2",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def remove_device(ws_client, device_id, config_entry_id):
    """Remove config entry from a device."""
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry_id,
            "device_id": device_id,
        }
    )
    response = await ws_client.receive_json()
    return response["success"]


async def test_device_remove_devices(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    registry: er.EntityRegistry = er.async_get(hass)
    entity = registry.entities["climate.hallway"]

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(entity.device_id)
    assert (
        await remove_device(
            await hass_ws_client(hass), device_entry.id, load_int.entry_id
        )
        is False
    )

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=load_int.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )
    assert (
        await remove_device(
            await hass_ws_client(hass), dead_device_entry.id, load_int.entry_id
        )
        is True
    )

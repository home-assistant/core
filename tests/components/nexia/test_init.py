"""The init tests for the nexia platform."""

import aiohttp

from homeassistant.components.nexia.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.setup import async_setup_component

from .util import async_init_integration

from tests.typing import WebSocketGenerator


async def test_setup_retry_client_os_error(hass: HomeAssistant) -> None:
    """Verify we retry setup on aiohttp.ClientOSError."""
    config_entry = await async_init_integration(hass, exception=aiohttp.ClientOSError)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_remove_devices(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can only remove a device that no longer exists."""
    await async_setup_component(hass, "config", {})
    config_entry = await async_init_integration(hass)
    entry_id = config_entry.entry_id
    device_registry = dr.async_get(hass)

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["sensor.nick_office_temperature"]

    live_zone_device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(live_zone_device_entry.id, entry_id)
    assert not response["success"]

    entity = registry.entities["sensor.master_suite_humidity"]
    live_thermostat_device_entry = device_registry.async_get(entity.device_id)
    response = await client.remove_device(live_thermostat_device_entry.id, entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "unused")},
    )
    response = await client.remove_device(dead_device_entry.id, entry_id)
    assert response["success"]

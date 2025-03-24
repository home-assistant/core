"""The init tests for the nexia platform."""

from unittest.mock import patch

import aiohttp

from homeassistant.components.nexia.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .util import async_init_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_setup_retry_client_os_error(hass: HomeAssistant) -> None:
    """Verify we retry setup on aiohttp.ClientOSError."""
    config_entry = await async_init_integration(hass, exception=aiohttp.ClientOSError)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we can only remove a device that no longer exists."""
    await async_setup_component(hass, "config", {})
    config_entry = await async_init_integration(hass)
    entry_id = config_entry.entry_id

    entity = entity_registry.entities["sensor.nick_office_temperature"]

    live_zone_device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(live_zone_device_entry.id, entry_id)
    assert not response["success"]

    entity = entity_registry.entities["sensor.master_suite_humidity"]
    live_thermostat_device_entry = device_registry.async_get(entity.device_id)
    response = await client.remove_device(live_thermostat_device_entry.id, entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "unused")},
    )
    response = await client.remove_device(dead_device_entry.id, entry_id)
    assert response["success"]


async def test_migrate_entry_minor_version_1_2(hass: HomeAssistant) -> None:
    """Test migrating a 1.1 config entry to 1.2."""
    with patch("homeassistant.components.nexia.async_setup_entry", return_value=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"},
            version=1,
            minor_version=1,
            unique_id=123456,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 1
        assert entry.minor_version == 2
        assert entry.unique_id == "123456"

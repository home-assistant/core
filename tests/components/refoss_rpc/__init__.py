"""The tests for refoss_rpc."""

from collections.abc import Mapping
from copy import deepcopy
from datetime import timedelta
from typing import Any
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.refoss_rpc.const import (
    DOMAIN,
    REFOSS_SENSORS_POLLING_INTERVAL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceEntry,
    DeviceRegistry,
    format_mac,
)

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_MAC = "123456789ABC"


async def set_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the refoss-rpc integration in Home Assistant."""
    data = {
        CONF_HOST: "1.1.1.1",
        CONF_MAC: "123456789ABC",
        "model": "r11",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def mutate_rpc_device_status(
    monkeypatch: pytest.MonkeyPatch,
    mock_rpc_device: Mock,
    top_level_key: str,
    key: str,
    value: Any,
) -> None:
    """Mutate status for rpc device."""
    new_status = deepcopy(mock_rpc_device.status)
    new_status[top_level_key][key] = value
    monkeypatch.setattr(mock_rpc_device, "status", new_status)


def inject_rpc_device_event(
    monkeypatch: pytest.MonkeyPatch,
    mock_rpc_device: Mock,
    event: Mapping[str, list[dict[str, Any]] | float],
) -> None:
    """Inject event for rpc device."""
    monkeypatch.setattr(mock_rpc_device, "event", event)
    mock_rpc_device.mock_event()


async def mock_polling_rpc_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Move time to create polling RPC sensors update event."""
    freezer.tick(timedelta(seconds=REFOSS_SENSORS_POLLING_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def register_entity(
    hass: HomeAssistant,
    domain: str,
    object_id: str,
    unique_id: str,
    config_entry: ConfigEntry | None = None,
    device_id: str | None = None,
) -> str:
    """Register enabled entity, return entity_id."""
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        f"{MOCK_MAC}-{unique_id}",
        suggested_object_id=object_id,
        config_entry=config_entry,
        device_id=device_id,
    )
    return f"{domain}.{object_id}"


def get_entity(
    hass: HomeAssistant,
    domain: str,
    unique_id: str,
) -> str | None:
    """Get refoss_rpc entity."""
    entity_registry = er.async_get(hass)
    return entity_registry.async_get_entity_id(
        domain, DOMAIN, f"{MOCK_MAC}-{unique_id}"
    )


def get_entity_state(hass: HomeAssistant, entity_id: str) -> str:
    """Return entity state."""
    entity = hass.states.get(entity_id)
    assert entity
    return entity.state


def register_device(
    device_registry: DeviceRegistry, config_entry: ConfigEntry
) -> DeviceEntry:
    """Register refoss_rpc device."""
    return device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, format_mac(MOCK_MAC))},
    )

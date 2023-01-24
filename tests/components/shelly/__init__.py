"""Tests for the Shelly integration."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest

from homeassistant.components.shelly.const import (
    CONF_SLEEP_PERIOD,
    DOMAIN,
    REST_SENSORS_UPDATE_INTERVAL,
    RPC_SENSORS_POLLING_INTERVAL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_MAC = "123456789ABC"


async def init_integration(
    hass: HomeAssistant,
    gen: int,
    model="SHSW-25",
    sleep_period=0,
    options: dict[str, Any] | None = None,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Shelly integration in Home Assistant."""
    data = {
        CONF_HOST: "192.168.1.37",
        CONF_SLEEP_PERIOD: sleep_period,
        "model": model,
        "gen": gen,
    }

    entry = MockConfigEntry(
        domain=DOMAIN, data=data, unique_id=MOCK_MAC, options=options
    )
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
    event: dict[str, dict[str, Any]],
) -> None:
    """Inject event for rpc device."""
    monkeypatch.setattr(mock_rpc_device, "event", event)
    mock_rpc_device.mock_event()


async def mock_rest_update(hass: HomeAssistant, seconds=REST_SENSORS_UPDATE_INTERVAL):
    """Move time to create REST sensors update event."""
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def mock_polling_rpc_update(hass: HomeAssistant):
    """Move time to create polling RPC sensors update event."""
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=RPC_SENSORS_POLLING_INTERVAL)
    )
    await hass.async_block_till_done()


def register_entity(
    hass: HomeAssistant,
    domain: str,
    object_id: str,
    unique_id: str,
    config_entry: ConfigEntry | None = None,
    capabilities: Mapping[str, Any] | None = None,
) -> str:
    """Register enabled entity, return entity_id."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        f"{MOCK_MAC}-{unique_id}",
        suggested_object_id=object_id,
        disabled_by=None,
        config_entry=config_entry,
        capabilities=capabilities,
    )
    return f"{domain}.{object_id}"


def register_device(device_reg, config_entry: ConfigEntry):
    """Register Shelly device."""
    device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, format_mac(MOCK_MAC))},
    )

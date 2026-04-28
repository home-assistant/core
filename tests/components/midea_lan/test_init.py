"""Tests for midea_lan __init__.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from midealocal.const import DeviceType, ProtocolVersion
import pytest

import homeassistant.components.midea_lan as midea_init
from homeassistant.components.midea_lan import update_listener
from homeassistant.components.midea_lan.const import CONF_KEY, CONF_MODEL, CONF_SUBTYPE
from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .conftest import DummyDevice


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup initialises the domain data."""
    assert await midea_init.async_setup(hass, {})


async def test_unload_entry_no_device(hass: HomeAssistant) -> None:
    """Test async_unload_entry succeeds when runtime_data is None."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    entry = MagicMock()
    entry.runtime_data = None
    assert await midea_init.async_unload_entry(hass, entry)


async def test_unload_entry_closes_device(hass: HomeAssistant) -> None:
    """Test async_unload_entry calls device.close when runtime_data is set."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    dev = DummyDevice(DeviceType.AC)
    entry = MagicMock()
    entry.runtime_data = dev

    assert await midea_init.async_unload_entry(hass, entry)
    assert ("close",) in dev.calls


async def test_unload_entry_returns_false_on_platform_failure(
    hass: HomeAssistant,
) -> None:
    """Test async_unload_entry returns False when platform unload fails."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    entry = MagicMock()
    entry.runtime_data = None

    assert not await midea_init.async_unload_entry(hass, entry)


async def test_update_listener_updates_device(hass: HomeAssistant) -> None:
    """Test update_listener updates registered runtime device."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    dev = DummyDevice(DeviceType.AC)
    entry = MagicMock()
    entry.options = {CONF_CUSTOMIZE: "x"}
    entry.runtime_data = dev

    await update_listener(hass, entry)

    assert ("set_customize", "x") in dev.calls


async def test_update_listener_no_device(hass: HomeAssistant) -> None:
    """Test update_listener no-op when device is missing."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    entry = MagicMock()
    entry.options = {}
    entry.runtime_data = None

    await update_listener(hass, entry)


async def test_update_listener_unload_fails(hass: HomeAssistant) -> None:
    """Test update_listener returns early when unload fails."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    entry = MagicMock()
    entry.options = {}
    entry.runtime_data = None

    await update_listener(hass, entry)

    # async_forward_entry_setups should not be called
    hass.config_entries.async_forward_entry_setups.assert_not_called()


async def test_async_setup_entry_paths(hass: HomeAssistant) -> None:
    """Test async_setup_entry for failure, success, and no-device return."""
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    entry = MagicMock()
    entry.data = {
        CONF_TYPE: DeviceType.AC,
        CONF_DEVICE_ID: 123,
        CONF_NAME: "n",
        CONF_TOKEN: "",
        CONF_KEY: "",
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_PORT: 6444,
        CONF_MODEL: "m",
        CONF_SUBTYPE: 0,
        CONF_PROTOCOL: ProtocolVersion.V3,
    }
    entry.options = {}
    with pytest.raises(ConfigEntryError):
        await midea_init.async_setup_entry(hass, entry)

    entry.data = {
        CONF_TYPE: DeviceType.AC,
        CONF_DEVICE_ID: 456,
        CONF_NAME: "good",
        CONF_TOKEN: "aa",
        CONF_KEY: "bb",
        CONF_IP_ADDRESS: "2.2.2.2",
        CONF_PORT: 6444,
        CONF_MODEL: "x",
        CONF_SUBTYPE: 1,
        CONF_PROTOCOL: ProtocolVersion.V2,
    }
    entry.options = {CONF_CUSTOMIZE: "c"}

    hass.async_add_executor_job = AsyncMock(return_value=DummyDevice(DeviceType.AC))
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    entry.async_on_unload = MagicMock()
    assert await midea_init.async_setup_entry(hass, entry)

    hass.async_add_executor_job = AsyncMock(return_value=None)
    with pytest.raises(ConfigEntryNotReady):
        await midea_init.async_setup_entry(hass, entry)

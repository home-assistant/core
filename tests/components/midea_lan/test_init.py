"""Tests for midea_lan __init__.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from midealocal.const import DeviceType, ProtocolVersion
import pytest

import homeassistant.components.midea_lan as midea_init
from homeassistant.components.midea_lan.const import CONF_KEY, CONF_SUBTYPE
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
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


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test async_unload_entry delegates to async_unload_platforms."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    entry = MagicMock()
    assert await midea_init.async_unload_entry(hass, entry)


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
    entry.options = {}

    hass.async_add_executor_job = AsyncMock(return_value=DummyDevice(DeviceType.AC))
    entry.async_on_unload = MagicMock()
    assert await midea_init.async_setup_entry(hass, entry)
    await entry.async_on_unload.call_args[0][0]()

    hass.async_add_executor_job = AsyncMock(return_value=None)
    with pytest.raises(ConfigEntryNotReady):
        await midea_init.async_setup_entry(hass, entry)

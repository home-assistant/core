"""Tests for midea_lan __init__.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from midealocal.const import DeviceType, ProtocolVersion
from midealocal.devices.ac import DeviceAttributes as ACAttributes
import pytest

import homeassistant.components.midea_lan as midea_init
from homeassistant.components.midea_lan import update_listener
from homeassistant.components.midea_lan.const import (
    CONF_KEY,
    CONF_MODEL,
    CONF_REFRESH_INTERVAL,
    CONF_SUBTYPE,
    DEVICES,
    DOMAIN,
)
from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady


class DummyDevice:
    """Simple fake Midea device for init tests."""

    def __init__(self, device_type: int) -> None:
        """Initialize fake device."""
        self.device_type = device_type
        self.device_id = 123
        self.calls: list[tuple] = []

    def set_customize(self, value: str) -> None:
        """Record customize call."""
        self.calls.append(("set_customize", value))

    def set_ip_address(self, value: str) -> None:
        """Record ip address call."""
        self.calls.append(("set_ip_address", value))

    def set_refresh_interval(self, value: int) -> None:
        """Record refresh interval call."""
        self.calls.append(("set_refresh_interval", value))

    def open(self) -> None:
        """Record open call."""
        self.calls.append(("open",))


async def test_init_async_setup_and_unload(hass: HomeAssistant) -> None:
    """Test async_setup and async_unload_entry paths."""
    assert await midea_init.async_setup(hass, {})

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    entry = MagicMock()
    assert await midea_init.async_unload_entry(hass, entry)


async def test_init_async_setup_switch_attribute_path(hass: HomeAssistant) -> None:
    """Test async_setup covers EXTRA_SWITCH attribute collection branch."""
    with patch.object(
        midea_init,
        "MIDEA_DEVICES",
        {
            DeviceType.AC: {
                "entities": {
                    ACAttributes.fan_speed: {"type": Platform.SWITCH},
                }
            }
        },
    ):
        assert await midea_init.async_setup(hass, {})


async def test_update_listener_updates_device(hass: HomeAssistant) -> None:
    """Test update_listener updates registered runtime device."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())

    dev = DummyDevice(DeviceType.AC)
    hass.data[DOMAIN] = {DEVICES: {123: dev}}
    entry = MagicMock()
    entry.data = {CONF_DEVICE_ID: 123}
    entry.options = {
        CONF_CUSTOMIZE: "x",
        CONF_IP_ADDRESS: "1.2.3.4",
        CONF_REFRESH_INTERVAL: 15,
    }

    await update_listener(hass, entry)

    assert ("set_customize", "x") in dev.calls
    assert ("set_ip_address", "1.2.3.4") in dev.calls
    assert ("set_refresh_interval", 15) in dev.calls


async def test_update_listener_no_device(hass: HomeAssistant) -> None:
    """Test update_listener no-op when device is missing."""
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())
    hass.data[DOMAIN] = {DEVICES: {}}

    entry = MagicMock()
    entry.data = {CONF_DEVICE_ID: 123}
    entry.options = {}

    await update_listener(hass, entry)


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
    entry.options = {CONF_REFRESH_INTERVAL: 10, CONF_CUSTOMIZE: "c"}

    hass.async_add_import_executor_job = AsyncMock(
        return_value=DummyDevice(DeviceType.AC)
    )
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    entry.async_on_unload = MagicMock()
    assert await midea_init.async_setup_entry(hass, entry)

    hass.async_add_import_executor_job = AsyncMock(return_value=None)
    with pytest.raises(ConfigEntryNotReady):
        await midea_init.async_setup_entry(hass, entry)

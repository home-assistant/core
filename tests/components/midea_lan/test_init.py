"""Tests for midea_lan __init__.py."""

from unittest.mock import patch

from midealocal.const import DeviceType, ProtocolVersion

from homeassistant.components.midea_lan.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_PORT,
    CONF_PROTOCOL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import DummyDevice

from tests.common import MockConfigEntry

_ENTRY_DATA = {
    CONF_DEVICE_ID: 123,
    CONF_IP_ADDRESS: "1.1.1.1",
    CONF_PORT: 6444,
    CONF_MODEL: "m",
    CONF_PROTOCOL: ProtocolVersion.V2,
}


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup initialises the domain data."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test async_unload_entry unloads platforms."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=DummyDevice(DeviceType.AC),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_v3_requires_token_and_key(
    hass: HomeAssistant,
) -> None:
    """Test V3 setup fails when token/key are missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_ID: 123,
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_PORT: 6444,
            CONF_MODEL: "m",
            CONF_PROTOCOL: ProtocolVersion.V3,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_paths(hass: HomeAssistant) -> None:
    """Test async_setup_entry for success and no-device return."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=DummyDevice(DeviceType.AC),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={**_ENTRY_DATA, CONF_DEVICE_ID: 456},
    )
    entry2.add_to_hass(hass)
    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry2.entry_id)
    assert entry2.state is ConfigEntryState.SETUP_RETRY

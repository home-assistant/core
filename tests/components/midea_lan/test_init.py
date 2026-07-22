"""Tests for midea_lan __init__.py."""

from unittest.mock import patch

from midealocal.const import DeviceType, ProtocolVersion

from homeassistant.components.midea_lan.const import CONF_KEY, CONF_SUBTYPE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
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
from homeassistant.setup import async_setup_component

from .conftest import DummyDevice
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry

_ENTRY_DATA = {
    CONF_DEVICE_ID: TEST_DEVICE_ID,
    CONF_NAME: "m",
    CONF_TYPE: DeviceType.AC,
    CONF_IP_ADDRESS: "1.1.1.1",
    CONF_PORT: 6444,
    CONF_MODEL: "m",
    CONF_PROTOCOL: ProtocolVersion.V2,
    CONF_TOKEN: "",
    CONF_KEY: "",
    CONF_SUBTYPE: 0,
}


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the midea_lan domain can be set up without any config entries."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test async_unload_entry unloads platforms and closes the device."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)
    device = DummyDevice(DeviceType.AC)
    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert device.daemon is True
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert ("close",) in device.calls


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
        data={**_ENTRY_DATA, CONF_DEVICE_ID: TEST_DEVICE_ID + 1},
    )
    entry2.add_to_hass(hass)
    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry2.entry_id)
    assert entry2.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_not_ready_on_connect_failure(
    hass: HomeAssistant,
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when connect returns False.

    The real device.connect() already catches SocketException/AuthException
    internally and reports failure by returning False; it never raises them.
    It can also leave the socket open in that case (e.g. when authentication
    fails), so the socket must be closed explicitly to avoid a ResourceWarning.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)
    device = DummyDevice(DeviceType.AC)
    with (
        patch(
            "homeassistant.components.midea_lan.device_selector",
            return_value=device,
        ),
        patch.object(device, "connect", return_value=False),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert ("close_socket",) in device.calls

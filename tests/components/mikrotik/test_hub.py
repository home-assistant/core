"""The tests for the Mikrotik device tracker platform."""
from __future__ import annotations

from homeassistant.components import mikrotik
from homeassistant.core import HomeAssistant

from . import setup_mikrotik_entry


async def test_info_routerboard(hass: HomeAssistant) -> None:
    """Test device firmware/model for routerboard routers."""

    entry_id = "mikrotik_entry_id"
    await setup_mikrotik_entry(hass, entry_id=entry_id)
    device = hass.data[mikrotik.DOMAIN][entry_id]

    assert device.firmware == "test_firmware"
    assert device.model == "test_model"


async def test_info_chr(hass: HomeAssistant) -> None:
    """Test device firmware/model for CHR routers."""

    entry_id = "mikrotik_entry_id"
    await setup_mikrotik_entry(hass, entry_id=entry_id, info_data=[])
    device = hass.data[mikrotik.DOMAIN][entry_id]

    assert device.firmware == ""
    assert device.model == ""

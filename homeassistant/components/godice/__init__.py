"""The godice integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import bleak
import godice

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SHELL

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

type DiceConfigEntry = ConfigEntry[DiceData]


@dataclass
class DiceData:
    """Runtime data to interact with GoDice."""

    dice: godice.Dice
    disconnected_by_request_flag: bool


async def async_setup_entry(hass: HomeAssistant, entry: DiceConfigEntry) -> bool:
    """Set up godice from a config entry."""
    _LOGGER.debug("Setup started")

    def on_disconnect_callback(_ble_data):
        _LOGGER.debug("on_disconnect_callback called")
        is_disconnected_by_request = entry.runtime_data.disconnected_by_request_flag
        if not is_disconnected_by_request:
            hass.create_task(hass.config_entries.async_reload(entry.entry_id))

    try:
        ble_device = bluetooth.async_ble_device_from_address(
            hass, entry.data[CONF_ADDRESS]
        )
        assert ble_device is not None
        client = bleak.BleakClient(
            ble_device, timeout=20, disconnected_callback=on_disconnect_callback
        )
        dice = godice.create(client, godice.Shell[entry.data[CONF_SHELL]])
        await dice.connect()
        await dice.pulse_led(
            pulse_count=2, on_time_ms=50, off_time_ms=20, rgb_tuple=(0, 255, 0)
        )
    except Exception as err:
        raise ConfigEntryNotReady("Device not found") from err

    entry.runtime_data = DiceData(dice, False)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DiceConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading entry")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # prevent disconnect callback from integration reloading when disconnected by a user
    entry.runtime_data.disconnected_by_request_flag = True
    dice = entry.runtime_data.dice
    await dice.disconnect()
    return unload_ok

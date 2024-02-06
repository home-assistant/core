"""Support for EQ3 devices."""

import asyncio
import logging

from eq3btsmart import Thermostat
from eq3btsmart.exceptions import Eq3Exception
from eq3btsmart.thermostat_config import ThermostatConfig

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_THERMOSTAT_CONNECTED, SIGNAL_THERMOSTAT_DISCONNECTED
from .models import Eq3Config, Eq3ConfigEntry

PLATFORMS = [
    Platform.CLIMATE,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle config entry setup."""

    mac_address: str = entry.data[CONF_MAC]
    name: str = entry.data[CONF_NAME]

    eq3_config = Eq3Config(
        mac_address=mac_address,
        name=name,
    )

    device = bluetooth.async_ble_device_from_address(
        hass, mac_address, connectable=True
    )

    if device is None:
        raise ConfigEntryNotReady(f"[{eq3_config.name}] Device could not be found")

    thermostat = Thermostat(
        thermostat_config=ThermostatConfig(
            mac_address=mac_address,
            name=name,
        ),
        ble_device=device,
    )

    eq3_config_entry = Eq3ConfigEntry(eq3_config=eq3_config, thermostat=thermostat)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = eq3_config_entry

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_create_background_task(
        hass, _run_thermostat(hass, entry), entry.entry_id
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle config entry unload."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        eq3_config_entry: Eq3ConfigEntry = hass.data[DOMAIN].pop(entry.entry_id)
        await eq3_config_entry.thermostat.async_disconnect()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry update."""

    await hass.config_entries.async_reload(entry.entry_id)


async def _run_thermostat(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Run the thermostat."""

    eq3_config_entry: Eq3ConfigEntry = hass.data[DOMAIN][entry.entry_id]

    await _reconnect_thermostat(hass, entry)

    while True:
        try:
            await eq3_config_entry.thermostat.async_get_status()
        except Eq3Exception as e:
            if not eq3_config_entry.thermostat.is_connected:
                _LOGGER.error(
                    "[%s] eQ-3 device disconnected",
                    eq3_config_entry.eq3_config.name,
                )
                async_dispatcher_send(
                    hass,
                    SIGNAL_THERMOSTAT_DISCONNECTED,
                    eq3_config_entry.eq3_config.mac_address,
                )
                await _reconnect_thermostat(hass, entry)
                continue

            _LOGGER.error(
                "[%s] Error updating eQ-3 device: %s",
                eq3_config_entry.eq3_config.name,
                e,
            )

        await asyncio.sleep(eq3_config_entry.eq3_config.scan_interval)


async def _reconnect_thermostat(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reconnect the thermostat."""

    eq3_config_entry: Eq3ConfigEntry = hass.data[DOMAIN][entry.entry_id]

    while True:
        try:
            await eq3_config_entry.thermostat.async_connect()
        except Eq3Exception:
            await asyncio.sleep(eq3_config_entry.eq3_config.scan_interval)
            continue

        _LOGGER.info(
            "[%s] eQ-3 device connected",
            eq3_config_entry.eq3_config.name,
        )

        async_dispatcher_send(
            hass,
            SIGNAL_THERMOSTAT_CONNECTED,
            eq3_config_entry.eq3_config.mac_address,
        )

        return

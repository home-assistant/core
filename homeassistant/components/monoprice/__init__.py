"""The Monoprice 6-Zone Amplifier integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from pymonoprice import Monoprice, get_monoprice
from serial import SerialException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_NOT_FIRST_RUN

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)

type MonopriceConfigEntry = ConfigEntry[MonopriceRuntimeData]


@dataclass
class MonopriceRuntimeData:
    """Data stored in the config entry for a Monoprice entry."""

    client: Monoprice
    first_run: bool


async def async_setup_entry(hass: HomeAssistant, entry: MonopriceConfigEntry) -> bool:
    """Set up Monoprice 6-Zone Amplifier from a config entry."""
    port = entry.data[CONF_PORT]

    try:
        monoprice = await hass.async_add_executor_job(get_monoprice, port)
    except SerialException as err:
        _LOGGER.error("Error connecting to Monoprice controller at %s", port)
        raise ConfigEntryNotReady from err

    # double negative to handle absence of value
    first_run = not bool(entry.data.get(CONF_NOT_FIRST_RUN))

    if first_run:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_NOT_FIRST_RUN: True}
        )

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    entry.runtime_data = MonopriceRuntimeData(
        client=monoprice,
        first_run=first_run,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MonopriceConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    def _cleanup(monoprice) -> None:
        """Destroy the Monoprice object.

        Destroying the Monoprice closes the serial connection, do it in an executor so the garbage
        collection does not block.
        """
        del monoprice

    await hass.async_add_executor_job(_cleanup, entry.runtime_data.client)

    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

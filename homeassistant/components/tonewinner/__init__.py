"""Set up Tonewinner from a config entry."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from tonewinner_rs232 import TonewinnerReceiver

from .const import CONF_BAUD_RATE, CONF_SERIAL_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

type TonewinnerConfigEntry = ConfigEntry[TonewinnerReceiver]


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Options updated, reloading integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant, entry: TonewinnerConfigEntry
) -> bool:
    """Set up Tonewinner from a config entry."""
    port = entry.data[CONF_SERIAL_PORT]
    baud = entry.data.get(CONF_BAUD_RATE, 9600)

    receiver = TonewinnerReceiver(port, baudrate=baud)
    await receiver.connect()
    await receiver.query_state()

    entry.runtime_data = receiver

    await hass.config_entries.async_forward_entry_setups(entry, ["media_player"])
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Tonewinner integration setup complete")
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TonewinnerConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Tonewinner integration")

    await hass.config_entries.async_forward_entry_unload(entry, "media_player")

    if entry.runtime_data:
        await entry.runtime_data.disconnect()

    _LOGGER.info("Tonewinner integration unloaded")
    return True

"""Set up Tonewinner from a config entry."""

import logging

from tonewinner_rs232 import TonewinnerReceiver

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import CONF_SERIAL_PORT, DOMAIN

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TonewinnerConfigEntry = ConfigEntry[TonewinnerReceiver]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TonewinnerConfigEntry) -> bool:
    """Set up Tonewinner from a config entry."""
    port = entry.data[CONF_SERIAL_PORT]

    receiver = TonewinnerReceiver(port)
    try:
        await receiver.connect()
        await receiver.query_state()
    except OSError as err:
        await receiver.disconnect()
        raise ConfigEntryNotReady(f"Unable to connect to {port}") from err

    _LOGGER.info("Connected to Tonewinner receiver on %s", port)

    entry.runtime_data = receiver

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TonewinnerConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.disconnect()
    return unload_ok

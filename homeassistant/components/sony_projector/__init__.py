"""The Sony Projector integration."""

import pysdcp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = [Platform.SWITCH]

type SonyProjectorConfigEntry = ConfigEntry[pysdcp.Projector]


async def async_setup_entry(
    hass: HomeAssistant, entry: SonyProjectorConfigEntry
) -> None:
    """Set up Sony Projector from a config entry."""
    projector = pysdcp.Projector(entry.data[CONF_HOST])
    try:
        await hass.async_add_executor_job(projector.get_power)
    # pySDCP raises bare Exception for timeouts and projector error replies.
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    entry.runtime_data = projector
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: SonyProjectorConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

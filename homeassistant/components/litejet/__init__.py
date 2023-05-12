"""Support for the LiteJet lighting system."""
import logging

import pylitejet
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_EXCLUDE_NAMES, CONF_INCLUDE_SWITCHES, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_PORT): cv.string,
                    vol.Optional(CONF_EXCLUDE_NAMES): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_INCLUDE_SWITCHES, default=False): cv.boolean,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LiteJet component."""
    if DOMAIN in config and not hass.config_entries.async_entries(DOMAIN):
        # No config entry exists and configuration.yaml config exists, trigger the import flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LiteJet via a config entry."""
    port = entry.data[CONF_PORT]

    try:
        system = await pylitejet.open(port)
    except pylitejet.LiteJetError as exc:
        raise ConfigEntryNotReady from exc

    def handle_connected_changed(connected: bool, reason: str) -> None:
        if connected:
            _LOGGER.info("Connected")
        else:
            _LOGGER.warning("Disconnected %s", reason)

    system.on_connected_changed(handle_connected_changed)

    async def handle_stop(event: Event) -> None:
        await system.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop)
    )

    hass.data[DOMAIN] = system

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a LiteJet config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await hass.data[DOMAIN].close()
        hass.data.pop(DOMAIN)

    return unload_ok

"""Support for the Transmission BitTorrent client API."""
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .client import TransmissionClientCoordinator
from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_TORRENT,
    SERVICE_REMOVE_TORRENT,
    SERVICE_START_TORRENT,
    SERVICE_STOP_TORRENT,
)

TRANS_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): cv.time_period,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    vol.All(cv.deprecated(DOMAIN), {DOMAIN: vol.All(cv.ensure_list, [TRANS_SCHEMA])}),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the Transmission Component from config."""
    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Transmission Component."""
    unique_id = f"{config_entry.data[CONF_HOST]}:{config_entry.data[CONF_PORT]}"
    hass.config_entries.async_update_entry(
        config_entry,
        title=f"{config_entry.data[CONF_NAME]} ({unique_id})",
        unique_id=unique_id,
    )

    coordinator = TransmissionClientCoordinator(hass, config_entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Transmission Entry from config_entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_START_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_STOP_TORRENT)
            del hass.data[DOMAIN]

    return unload_ok

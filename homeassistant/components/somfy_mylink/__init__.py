"""Component for the Somfy MyLink device supporting the Synergy API."""

import logging

from somfy_mylink_synergy import SomfyMyLinkSynergy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SYSTEM_ID, DATA_SOMFY_MYLINK, DOMAIN, MYLINK_STATUS, PLATFORMS

UNDO_UPDATE_LISTENER = "undo_update_listener"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Somfy MyLink from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config = entry.data
    somfy_mylink = SomfyMyLinkSynergy(
        config[CONF_SYSTEM_ID], config[CONF_HOST], config[CONF_PORT]
    )

    try:
        mylink_status = await somfy_mylink.status_info()
    except TimeoutError as ex:
        raise ConfigEntryNotReady(
            "Unable to connect to the Somfy MyLink device, please check your settings"
        ) from ex

    if not mylink_status or "error" in mylink_status:
        _LOGGER.error(
            "Somfy Mylink failed to setup because of an error: %s",
            mylink_status.get("error", {}).get(
                "message", "Empty response from mylink device"
            ),
        )
        return False

    if "result" not in mylink_status:
        raise ConfigEntryNotReady("The Somfy MyLink device returned an empty result")

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_SOMFY_MYLINK: somfy_mylink,
        MYLINK_STATUS: mylink_status,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

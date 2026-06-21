"""Component for the Somfy MyLink device supporting the Synergy API."""

from dataclasses import dataclass
import logging
from typing import Any

from somfy_mylink_synergy import SomfyMyLinkSynergy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SYSTEM_ID, PLATFORMS

_LOGGER = logging.getLogger(__name__)

type SomfyMyLinkConfigEntry = ConfigEntry[SomfyMyLinkRuntimeData]


@dataclass
class SomfyMyLinkRuntimeData:
    """Runtime data for Somfy MyLink."""

    somfy_mylink: SomfyMyLinkSynergy
    mylink_status: dict[str, Any]


async def async_setup_entry(hass: HomeAssistant, entry: SomfyMyLinkConfigEntry) -> bool:
    """Set up Somfy MyLink from a config entry."""
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

    entry.runtime_data = SomfyMyLinkRuntimeData(
        somfy_mylink=somfy_mylink,
        mylink_status=mylink_status,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SomfyMyLinkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

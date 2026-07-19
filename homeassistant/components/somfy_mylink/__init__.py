"""The Somfy MyLink integration."""

from dataclasses import dataclass

from pysomfymylink import (
    Shade,
    SomfyMyLink,
    SomfyMyLinkApiError,
    SomfyMyLinkConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SYSTEM_ID, DEFAULT_PORT, PLATFORMS

type SomfyMyLinkConfigEntry = ConfigEntry[SomfyMyLinkRuntimeData]


@dataclass
class SomfyMyLinkRuntimeData:
    """Runtime data for Somfy MyLink."""

    somfy_mylink: SomfyMyLink
    shades: list[Shade]


async def async_setup_entry(hass: HomeAssistant, entry: SomfyMyLinkConfigEntry) -> bool:
    """Set up Somfy MyLink from a config entry."""
    somfy_mylink = SomfyMyLink(
        entry.data[CONF_HOST],
        entry.data[CONF_SYSTEM_ID],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
    )

    try:
        shades = await somfy_mylink.status_info()
    except SomfyMyLinkConnectionError as ex:
        raise ConfigEntryNotReady(
            "Unable to connect to the Somfy MyLink device, please check your settings"
        ) from ex
    except SomfyMyLinkApiError as ex:
        raise ConfigEntryNotReady(
            f"The Somfy MyLink device rejected the request ({ex.message}), "
            "please check your System ID"
        ) from ex

    if not shades:
        raise ConfigEntryNotReady("The Somfy MyLink device returned no covers")

    entry.runtime_data = SomfyMyLinkRuntimeData(
        somfy_mylink=somfy_mylink,
        shades=shades,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SomfyMyLinkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

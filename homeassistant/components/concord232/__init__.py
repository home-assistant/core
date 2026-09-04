"""The Concord232 integration."""

import asyncio

from yarl import URL

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_IMPORT_PLATFORM,
    CONF_IMPORTED_PLATFORMS,
    DATA_IMPORT_LOCK,
    DOMAIN,
)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]


def build_url(host: str, port: int) -> str:
    """Return the server url for the stored connection settings."""
    # URL.build brackets IPv6 hosts correctly
    return str(URL.build(scheme="http", host=host, port=port))


def entry_platforms(entry: ConfigEntry) -> list[Platform]:
    """Return the platforms this entry exposes.

    Imported entries are restricted to the platforms their YAML actually
    configured; entries created through the UI expose everything.
    """
    return [
        Platform(platform) for platform in entry.data.get(CONF_IMPORTED_PLATFORMS, [])
    ] or PLATFORMS


async def async_import_yaml(
    hass: HomeAssistant, config: ConfigType, platform: Platform
) -> None:
    """Import one platform's YAML configuration through the config flow.

    The alarm and binary sensor platforms set up concurrently and import
    the same server. The lock spans the entire flow, including entry
    registration, so the first import creates the entry and the second
    sees it and merges into it instead of creating a duplicate.
    """
    lock = hass.data.setdefault(DATA_IMPORT_LOCK, asyncio.Lock())
    async with lock:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={**config, CONF_IMPORT_PLATFORM: platform.value},
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Concord232 from a config entry."""
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, entry_platforms(entry))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, entry_platforms(entry)
    )

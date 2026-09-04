"""The Tewke integration."""

from typing import TYPE_CHECKING

import pytewke
from pytewke.error import PyTewkeDiscoveryError

from homeassistant.const import CONF_HOST, Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, LOGGER
from .coordinator import TewkeCoordinator
from .data import TewkeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TewkeConfigEntry

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TewkeConfigEntry,
) -> bool:
    """Set up a Tewke device from a config entry."""
    tap = pytewke.Tap(entry.data[CONF_HOST])

    try:
        await tap.discover()
    except PyTewkeDiscoveryError as err:
        await tap.close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="discovery_error",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err

    if tap.wall_dock_id is None:
        await tap.close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="missing_wall_dock_id",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        )

    entry.async_on_unload(tap.close)

    tewke_coordinator = TewkeCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        config_entry=entry,
    )

    entry.runtime_data = TewkeData(
        host=entry.data[CONF_HOST],
        tap=tap,
        coordinator=tewke_coordinator,
    )

    await tewke_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    remove_listener_callback = entry.add_update_listener(async_reload_entry)
    entry.async_on_unload(remove_listener_callback)
    entry.async_on_unload(tewke_coordinator.cancel_observation_timeout)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TewkeConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: TewkeConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)

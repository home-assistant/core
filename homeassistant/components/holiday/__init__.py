"""The Holiday integration."""

from __future__ import annotations

from functools import partial

from holidays import country_holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import SetupPhases, async_pause_setup

from .const import CONF_CATEGORIES, CONF_PROVINCE

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Holiday from a config entry."""
    country: str = entry.data[CONF_COUNTRY]
    province: str | None = entry.data.get(CONF_PROVINCE)
    categories: list[str] | None = entry.options.get(CONF_CATEGORIES)

    # We only import here to ensure that that its not imported later
    # in the event loop since the platforms will call country_holidays
    # which loads python code from disk.
    with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
        # import executor job is used here because multiple integrations use
        # the holidays library and it is not thread safe to import it in parallel
        # https://github.com/python/cpython/issues/83065
        await hass.async_add_import_executor_job(
            partial(country_holidays, country, subdiv=province, categories=categories)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

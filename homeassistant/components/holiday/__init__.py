"""The Holiday integration."""

from functools import partial

from holidays import country_holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import SetupPhases, async_pause_setup

from .const import CONF_CATEGORIES, CONF_PROVINCE, COUNTRY_OPTIONS

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate an old config entry."""
    if entry.version == 1 and entry.minor_version < 2:
        options = dict(entry.options)
        try:
            country_data = await hass.async_add_import_executor_job(
                country_holidays, entry.data[CONF_COUNTRY]
            )
        except NotImplementedError:
            supported_options = {}
        else:
            supported_options = country_data.get_supported_options()
        # Store the defaults, so equal calendars are found as duplicates
        for option in COUNTRY_OPTIONS:
            if option in supported_options:
                options.setdefault(option, supported_options[option])
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

"""Sensor to indicate whether the current day is a workday."""

from datetime import timedelta
from typing import Any, cast

from holidays import DateLike, HolidayBase, country_holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ADD_HOLIDAYS,
    CONF_CATEGORY,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    COUNTRY_OPTIONS,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SECTION_COUNTRY_SETTINGS,
    SECTION_CUSTOM_HOLIDAYS,
)
from .services import async_setup_services
from .util import (
    add_remove_custom_holidays,
    async_validate_country_and_province,
    get_holidays_object,
    validate_dates,
)

type WorkdayConfigEntry = ConfigEntry[HolidayBase]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Workday integration."""

    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> None:
    """Set up Workday from a config entry."""

    custom_holidays: dict[str, list[str]] = entry.options[SECTION_CUSTOM_HOLIDAYS]
    country_settings: dict[str, Any] = entry.options.get(SECTION_COUNTRY_SETTINGS, {})
    calc_add_holidays = cast(
        list[DateLike], validate_dates(custom_holidays[CONF_ADD_HOLIDAYS])
    )
    calc_remove_holidays: list[str] = validate_dates(
        custom_holidays[CONF_REMOVE_HOLIDAYS]
    )
    categories: list[str] | None = country_settings.get(CONF_CATEGORY)
    country: str | None = entry.options.get(CONF_COUNTRY)
    days_offset: int = int(entry.options[CONF_OFFSET])
    language: str | None = country_settings.get(CONF_LANGUAGE)
    province: str | None = country_settings.get(CONF_PROVINCE)
    year: int = (dt_util.now() + timedelta(days=days_offset)).year

    await async_validate_country_and_province(hass, entry, country, province)

    entry.runtime_data = await hass.async_add_executor_job(
        get_holidays_object,
        country,
        province,
        year,
        language,
        categories,
        country_settings,
    )

    add_remove_custom_holidays(
        hass, entry, country, calc_add_holidays, calc_remove_holidays
    )

    LOGGER.debug("Found the following holidays for your configuration:")
    for holiday_date, name in sorted(entry.runtime_data.items()):
        # Make explicit str variable to avoid "Incompatible types in assignment"
        _holiday_string = holiday_date.strftime("%Y-%m-%d")
        LOGGER.debug("%s %s", _holiday_string, name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> None:
    """Unload Workday config entry."""

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> None:
    """Migrate old config entry."""

    if entry.version == 1 and entry.minor_version == 1:
        # By keeping name in the data, it's enough to bump the minor version
        hass.config_entries.async_update_entry(
            entry,
            minor_version=2,
        )

    if entry.version == 1:
        options = dict(entry.options)
        options[SECTION_CUSTOM_HOLIDAYS] = {
            CONF_ADD_HOLIDAYS: options.pop(CONF_ADD_HOLIDAYS),
            CONF_REMOVE_HOLIDAYS: options.pop(CONF_REMOVE_HOLIDAYS),
        }
        if country_settings := {
            key: options.pop(key)
            for key in (CONF_PROVINCE, CONF_LANGUAGE, CONF_CATEGORY)
            if key in options
        }:
            options[SECTION_COUNTRY_SETTINGS] = country_settings
        hass.config_entries.async_update_entry(
            entry, options=options, version=2, minor_version=1
        )

    if entry.version == 2 and entry.minor_version < 2:
        options = dict(entry.options)
        if country := options.get(CONF_COUNTRY):
            try:
                country_data = await hass.async_add_import_executor_job(
                    country_holidays, country
                )
            except NotImplementedError:
                supported_options = {}
            else:
                supported_options = country_data.get_supported_options()
            # Store the defaults, so equal entries are found as duplicates
            country_settings = dict(options.get(SECTION_COUNTRY_SETTINGS, {}))
            for option in COUNTRY_OPTIONS:
                if option in supported_options:
                    country_settings.setdefault(option, supported_options[option])
            if country_settings:
                options[SECTION_COUNTRY_SETTINGS] = country_settings
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)

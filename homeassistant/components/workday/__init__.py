"""Sensor to indicate whether the current day is a workday."""

from datetime import timedelta
from typing import cast

from holidays import DateLike, HolidayBase
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ADD_HOLIDAYS,
    CONF_CATEGORY,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .util import (
    add_remove_custom_holidays,
    async_validate_country_and_province,
    get_holidays_object,
    validate_dates,
)

type WorkdayConfigEntry = ConfigEntry[HolidayBase]

SERVICE_CHECK_DATE = "check_date"
CHECK_DATE = "check_date"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Workday integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CHECK_DATE,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema={vol.Required(CHECK_DATE): cv.date},
        func="check_date",
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> bool:
    """Set up Workday from a config entry."""

    calc_add_holidays = cast(
        list[DateLike], validate_dates(entry.options[CONF_ADD_HOLIDAYS])
    )
    calc_remove_holidays: list[str] = validate_dates(
        entry.options[CONF_REMOVE_HOLIDAYS]
    )
    categories: list[str] | None = entry.options.get(CONF_CATEGORY)
    country: str | None = entry.options.get(CONF_COUNTRY)
    days_offset: int = int(entry.options[CONF_OFFSET])
    language: str | None = entry.options.get(CONF_LANGUAGE)
    province: str | None = entry.options.get(CONF_PROVINCE)
    year: int = (dt_util.now() + timedelta(days=days_offset)).year

    await async_validate_country_and_province(hass, entry, country, province)

    entry.runtime_data = await hass.async_add_executor_job(
        get_holidays_object, country, province, year, language, categories
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> bool:
    """Unload Workday config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> bool:
    """Migrate old config entry."""

    if entry.version == 1 and entry.minor_version == 1:
        # By keeping name in the data, it's enough to bump the minor version
        hass.config_entries.async_update_entry(
            entry,
            minor_version=2,
        )

    return True

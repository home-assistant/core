"""Sensor to indicate whether the current day is a workday."""
from __future__ import annotations

from typing import Any

import holidays
from holidays import HolidayBase
import voluptuous as vol

from homeassistant.const import CONF_NAME, WEEKDAYS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

DOMAIN = "workday"

ALLOWED_DAYS = WEEKDAYS + ["holiday"]

CONF_COUNTRY = "country"
CONF_PROVINCE = "province"
CONF_WORKDAYS = "workdays"
CONF_EXCLUDES = "excludes"
CONF_OFFSET = "days_offset"
CONF_ADD_HOLIDAYS = "add_holidays"
CONF_REMOVE_HOLIDAYS = "remove_holidays"

# By default, Monday - Friday are workdays
DEFAULT_WORKDAYS = ["mon", "tue", "wed", "thu", "fri"]
# By default, public holidays, Saturdays and Sundays are excluded from workdays
DEFAULT_EXCLUDES = ["sat", "sun", "holiday"]
DEFAULT_NAME = "Workday Sensor"
DEFAULT_OFFSET = 0


def valid_country(value: Any) -> str:
    """Validate that the given country is supported."""
    value = cv.string(value)
    all_supported_countries = holidays.list_supported_countries()

    try:
        raw_value = value.encode("utf-8")
    except UnicodeError as err:
        raise vol.Invalid(
            "The country name or the abbreviation must be a valid UTF-8 string."
        ) from err
    if not raw_value:
        raise vol.Invalid("Country name or the abbreviation must not be empty.")
    if value not in all_supported_countries:
        raise vol.Invalid("Country is not supported.")
    return value


def valid_province_for_country(value: dict[str, Any]) -> dict[str, Any]:
    """Validate that, if the given value object has a province, the province is valid for the country."""
    if CONF_PROVINCE in value:
        try:
            # it is safe to get CONF_COUNTRY since we've already checked that it is present
            # in the first item of the WORKDAY_SCHEMA
            holidays.country_holidays(value[CONF_COUNTRY], subdiv=value[CONF_PROVINCE])
        except NotImplementedError as exc:
            raise vol.Invalid(
                f"Province {value[CONF_PROVINCE]} is not supported for country {value[CONF_COUNTRY]}."
            ) from exc
    return value


DATE_VALIDATOR = HolidayBase().__keytransform__


WORKDAY_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_COUNTRY): valid_country,
            vol.Optional(CONF_EXCLUDES, default=DEFAULT_EXCLUDES): vol.All(
                cv.ensure_list, [vol.In(ALLOWED_DAYS)]
            ),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): vol.Coerce(int),
            vol.Optional(CONF_PROVINCE): cv.string,
            vol.Optional(CONF_WORKDAYS, default=DEFAULT_WORKDAYS): vol.All(
                cv.ensure_list, [vol.In(ALLOWED_DAYS)]
            ),
            vol.Optional(CONF_ADD_HOLIDAYS, default=[]): vol.All(
                cv.ensure_list, [DATE_VALIDATOR]
            ),
            vol.Optional(CONF_REMOVE_HOLIDAYS, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
        }
    ),
    valid_province_for_country,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [WORKDAY_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Workday component."""
    if DOMAIN not in config:
        return True

    for workday_conf in config[DOMAIN]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.BINARY_SENSOR, DOMAIN, workday_conf, config
            )
        )

    return True

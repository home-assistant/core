"""Tests the Home Assistant workday binary sensor."""
from homeassistant.components.workday.const import (  # CONF_ADVANCED,; DOMAIN,; ERR_NO_COUNTRY,; ERR_NO_SUBCOUNTRY,
    CONF_ADD_HOLIDAYS,
    CONF_COUNTRY,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_STATE,
    CONF_SUBCOUNTRY,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_NAME,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
)
from homeassistant.const import CONF_NAME


def create_workday_test_data(
    country,
    subcountry=None,
    province=None,
    state=None,
    name=DEFAULT_NAME,
    workdays=DEFAULT_WORKDAYS,
    excludes=DEFAULT_EXCLUDES,
    days_offset=DEFAULT_OFFSET,
):
    """Generate Workday configuration dict."""
    return {
        CONF_COUNTRY: country,
        CONF_SUBCOUNTRY: subcountry,
        CONF_PROVINCE: province,
        CONF_STATE: state,
        CONF_NAME: name,
        CONF_WORKDAYS: workdays,
        CONF_EXCLUDES: excludes,
        CONF_OFFSET: days_offset,
    }


def create_workday_test_options(add_holidays=None, remove_holidays=None):
    """Generate Workday options dict."""
    options = {}
    if add_holidays:
        options[CONF_ADD_HOLIDAYS] = add_holidays
    if remove_holidays:
        options[CONF_REMOVE_HOLIDAYS] = remove_holidays

    return options

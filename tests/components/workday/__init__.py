"""Tests the Home Assistant workday binary sensor."""
from homeassistant.components.workday.const import (  # CONF_ADVANCED,; DOMAIN,; ERR_NO_COUNTRY,; ERR_NO_SUBCOUNTRY,; DEFAULT_NAME,
    CONF_ADD_HOLIDAYS,
    CONF_ADVANCED,
    CONF_COUNTRY,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_STATE,
    CONF_SUBCOUNTRY,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
)
from homeassistant.const import CONF_NAME


def create_workday_test_data(
    country: str,
    subcountry: str = None,
    province: str = None,
    state: str = None,
    # name=DEFAULT_NAME,
    advanced_config: bool = False,
    workdays: dict[str] = DEFAULT_WORKDAYS,
    excludes: dict[str] = DEFAULT_EXCLUDES,
    days_offset: int = DEFAULT_OFFSET,
):
    """Generate Workday configuration dict."""
    advanced_data = {
        CONF_COUNTRY: country,
        CONF_PROVINCE: province,
        CONF_STATE: state,
        CONF_WORKDAYS: workdays,
        CONF_EXCLUDES: excludes,
        CONF_OFFSET: days_offset,
    }
    if province:
        bracket = f" ({province})"
        advanced_data[CONF_SUBCOUNTRY] = province
    elif state:
        bracket = f" ({state})"
        advanced_data[CONF_SUBCOUNTRY] = state
    else:
        bracket = ""
        advanced_data[CONF_SUBCOUNTRY] = subcountry

    if advanced_config:
        advanced_data[CONF_ADVANCED] = True

    advanced_data[CONF_NAME] = f"Workday {country}{bracket}"

    return advanced_data


def create_workday_test_options(add_holidays=None, remove_holidays=None):
    """Generate Workday options dict."""
    options = {}
    if add_holidays:
        options[CONF_ADD_HOLIDAYS] = add_holidays
    if remove_holidays:
        options[CONF_REMOVE_HOLIDAYS] = remove_holidays

    return options


def create_flow_basic_data(
    country: str,
    subcountry: str = None,
    advanced_config: bool = False,
):
    """Generate Workday configuration dict."""
    basic_data = {
        CONF_COUNTRY: country,
        CONF_SUBCOUNTRY: subcountry,
    }

    if advanced_config:
        basic_data[CONF_ADVANCED] = True

    return basic_data


def create_flow_advanced_data(
    workdays: dict[str] = DEFAULT_WORKDAYS,
    excludes: dict[str] = DEFAULT_EXCLUDES,
    days_offset: int = DEFAULT_OFFSET,
):
    """Generate Workday configuration dict."""
    return {
        CONF_WORKDAYS: workdays,
        CONF_EXCLUDES: excludes,
        CONF_OFFSET: days_offset,
    }

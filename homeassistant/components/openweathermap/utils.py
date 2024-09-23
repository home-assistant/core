"""Util functions for OpenWeatherMap."""

from typing import Any

from pyopenweathermap import RequestError, create_owm_client

from homeassistant.const import CONF_LANGUAGE, CONF_MODE

from .const import DEFAULT_LANGUAGE, DEFAULT_OWM_MODE

OPTION_DEFAULTS = {CONF_LANGUAGE: DEFAULT_LANGUAGE, CONF_MODE: DEFAULT_OWM_MODE}


async def validate_api_key(api_key, mode):
    """Validate API key."""
    api_key_valid = None
    errors, description_placeholders = {}, {}
    try:
        owm_client = create_owm_client(api_key, mode)
        api_key_valid = await owm_client.validate_key()
    except RequestError as error:
        errors["base"] = "cannot_connect"
        description_placeholders["error"] = str(error)

    if api_key_valid is False:
        errors["base"] = "invalid_api_key"

    return errors, description_placeholders


def build_data_and_options(
    combined_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split combined data and options."""
    data = {k: v for k, v in combined_data.items() if k not in OPTION_DEFAULTS}
    options = {
        option: combined_data.get(option, default)
        for option, default in OPTION_DEFAULTS.items()
    }
    return (data, options)

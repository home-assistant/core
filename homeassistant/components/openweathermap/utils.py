"""Util functions for OpenWeatherMap."""

from typing import Any

from pyopenweathermap import OWMClient, RequestError

from homeassistant.const import CONF_LANGUAGE, CONF_MODE

from .const import DEFAULT_LANGUAGE, DEFAULT_OWM_MODE

OPTIONS_KEYS = {CONF_LANGUAGE, CONF_MODE}


async def validate_api_key(api_key, mode):
    """Validate API key."""
    api_key_valid = None
    errors, description_placeholders = {}, {}
    try:
        owm_client = OWMClient(api_key, mode)
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
    data = {k: v for k, v in combined_data.items() if k not in OPTIONS_KEYS}
    options = {k: v for k, v in combined_data.items() if k in OPTIONS_KEYS}
    if CONF_LANGUAGE not in options:
        options[CONF_LANGUAGE] = DEFAULT_LANGUAGE
    if CONF_MODE not in options:
        options[CONF_MODE] = DEFAULT_OWM_MODE
    return (data, options)

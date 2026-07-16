"""Util functions for OpenWeatherMap."""

from typing import Any

from pyopenweathermap import RequestError, create_owm_client
from pyopenweathermap.client.onecall_client import OWMOneCallClient

from homeassistant.const import CONF_LANGUAGE, CONF_MODE

from .const import DEFAULT_LANGUAGE, DEFAULT_OWM_MODE, OWM_MODE_V40

OPTION_DEFAULTS = {CONF_LANGUAGE: DEFAULT_LANGUAGE, CONF_MODE: DEFAULT_OWM_MODE}


class OWMOneCallClientV4(OWMOneCallClient):
    """OWM client for One Call API 4.0."""

    def _get_url(self, lat: float, lon: float) -> str:
        return (
            "https://api.openweathermap.org/data/4.0/onecall?"
            f"lat={lat}&"
            f"lon={lon}&"
            f"appid={self.api_key}&"
            f"units={self.units}&"
            f"lang={self.lang}"
        )


def get_owm_client(api_key: str, mode: str, language: str = DEFAULT_LANGUAGE) -> Any:
    """Get the OWM client."""
    if mode == OWM_MODE_V40:
        return OWMOneCallClientV4(api_key, mode, lang=language)
    return create_owm_client(api_key, mode, lang=language)


async def validate_api_key(api_key, mode):
    """Validate API key."""
    api_key_valid = None
    errors, description_placeholders = {}, {}
    try:
        owm_client = get_owm_client(api_key, mode)
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

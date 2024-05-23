"""Util functions for OpenWeatherMap."""

from pyopenweathermap import OWMClient, RequestError


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

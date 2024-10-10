"""Common utility functions for the Transport for London integration."""

from collections.abc import Callable
from urllib.error import HTTPError, URLError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def call_tfl_api[*_Ts, _T](
    hass: HomeAssistant, target: Callable[[*_Ts], _T], *args: *_Ts
) -> _T:
    """Execute a call to TfL using the tflwrapper library using common error handling."""
    try:
        return_val = await hass.async_add_executor_job(target, *args)
    except HTTPError as exception:
        # TfL's API returns a 429 if you pass an invalid app_key, but we also check
        # for other reasonable error codes in case their behaviour changes
        error_code = exception.code
        if error_code in (429, 401, 403):
            raise InvalidAuth from exception
        raise
    except URLError as exception:
        raise CannotConnect from exception

    return return_val


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

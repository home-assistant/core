"""Config flow for the Firefly III integration."""

from __future__ import annotations

import logging
from typing import Any

from pyfirefly import Firefly, FireflyAuthenticationError, FireflyConnectionError
import voluptuous as vol

from homeassistant.components.water_heater import HomeAssistant
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_HOST, default="http://192.168.2.102:8883"
        ): str,  # TODO: clean this up later!
        vol.Required(
            CONF_API_KEY,
            default="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiNDMyNTVlZGMxZjkwZTA3OWFiYzk1YmM1N2Y3NGY1ZWE1Y2ZmNTNjNmI3YjZjZWI3ZjEwNzlmZTljOTYxZjk0MDliNGUzNGMyZDQ5MDI2MzAiLCJpYXQiOjE3NTAwOTUzNTAuNzkyMTYzLCJuYmYiOjE3NTAwOTUzNTAuNzkyMTY5LCJleHAiOjE3ODE2MzEzNTAuNDA0NjY5LCJzdWIiOiIxIiwic2NvcGVzIjpbXX0.yoADj8gmZt6lBUL3n4M82zKaZiPy5mWaW5Kr67yJKx3WIRdGsCEw8Nl5dKxv-TzydgMFTQYQjgkfWRX-Lw3Do8kGtMWwd1TVw5bb5UtVaH43NyZz5owjywgLn6BFwpA9Z25pcwF5H_1YqUb0Y5RJFeB5Y_13-T8r9LS3oELHkj8jB6dicmtEvL1fs31sHO19j8k5PkrziQ4Vp1N6Cnqo2LYU594zBGnWdyeN0LkNVeh3uxb0wLcLnD2GybPg1W518PzXez8dCCLt_FbTuIHVKQAHmfMp-hWWj0wT8hzeocmuqSqScfsrbtSrL2FvH6z3y6a4tT1XXIifAxq5RBwYNv8KklmEjWUMF1AftBCz3UDP4wZ6swFILTI7CpnYx3XrH0AGhwrlUwO3OpDFS_5Kd0hIAkkuQTrDY2RPut43i-VPJ49SqyXctq552QF6czasuunvCoxU3zl9VKd8xSooUS3Ap8woHp7ANflXGla2IZu2D1Ft4PVdC-i0p9y3eBLdySaBS1uFK_EkdDWm6lMcGEcUJhfAu2J_dwiuRxehvpmm31dM1BVdV9U5xjxoPDu2m0L2bVKwmvGVeRTAhKKxnWcnb8LxnAE1Oa_DfalSMvYX4DHx53bbvO2BLoA55wCjxbmMPi71981pHJ-l2OyXR2Q8HQY8ZKAUCv0mCRy7IXs",
        ): str,  # TODO: clean this up later!
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect."""

    client = Firefly(
        api_url=data[CONF_HOST],
        api_key=data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    try:
        await client.get_about()
    except FireflyAuthenticationError:
        raise InvalidAuth from None
    except FireflyConnectionError as err:
        raise CannotConnect from err
    except FireflyTimeout as err:
        raise FireflyTimeout from err

    return True


class FireflyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Firefly III."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_API_KEY])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class FireflyTimeout(HomeAssistantError):
    """Error to indicate a timeout occurred."""

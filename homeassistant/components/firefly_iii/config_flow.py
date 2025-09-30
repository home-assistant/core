"""Config flow for the Firefly III integration."""

from __future__ import annotations

import logging
from typing import Any

from pyfirefly import (
    Firefly,
    FireflyAuthenticationError,
    FireflyConnectionError,
    FireflyTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_API_KEY): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect."""

    try:
        client = Firefly(
            api_url=data[CONF_URL],
            api_key=data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        )
        await client.get_about()
    except FireflyAuthenticationError:
        raise InvalidAuth from None
    except FireflyConnectionError as err:
        raise CannotConnect from err
    except FireflyTimeoutError as err:
        raise FireflyClientTimeout from err

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
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            try:
                await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except FireflyClientTimeout:
                errors["base"] = "timeout_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

                return self.async_create_entry(
                    title=user_input[CONF_URL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class FireflyClientTimeout(HomeAssistantError):
    """Error to indicate a timeout occurred."""

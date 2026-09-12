"""Config flow for the Noonlight integration."""

from typing import Any

from noonlight_dispatch import (
    NoonlightAuthError,
    NoonlightClient,
    NoonlightConnectionError,
    NoonlightResponseError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN


class _CannotConnect(Exception):
    """Credentials step could not reach Noonlight."""


class _InvalidAuth(Exception):
    """Noonlight rejected the supplied token."""


async def _validate_credentials(hass: HomeAssistant, token: str) -> None:
    """Probe Noonlight to confirm the token works, without dispatching.

    A GET against a bogus alarm id has no side effects: a 401 means the token
    is bad, a 404 means we are reachable and authorised, and a 5xx outage or
    429 rate-limit means Noonlight is not answering normally (treated as a
    connection problem so we do not create an entry against a broken backend).
    """
    api = NoonlightClient(get_async_client(hass), token)
    try:
        await api.get_alarm_status("connection-test")
    except NoonlightAuthError as err:
        raise _InvalidAuth from err
    except NoonlightConnectionError as err:
        raise _CannotConnect from err
    except NoonlightResponseError as err:
        if err.status_code != 404:
            raise _CannotConnect from err


class NoonlightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Noonlight UI setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect and validate the Noonlight API token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate_credentials(self.hass, user_input[CONF_API_TOKEN])
            except _InvalidAuth:
                errors["base"] = "invalid_auth"
            except _CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Noonlight",
                    data={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

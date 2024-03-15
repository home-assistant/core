"""Config flow for SimpleFIN integration."""

from collections.abc import Mapping
from typing import Any

from simplefin4py import SimpleFin
from simplefin4py.exceptions import (
    SimpleFinAuthError,
    SimpleFinClaimError,
    SimpleFinInvalidAccountURLError,
    SimpleFinInvalidClaimTokenError,
    SimpleFinPaymentRequiredError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN

from .const import CONF_ACCESS_URL, DOMAIN, LOGGER


async def _validate_or_obtain_access_url(input_string: str) -> str:
    """Validate the input string as an access URL or a claim token and fetch data using SimpleFin.

    Args:
        input_string (str): The input_string will either be a URL or a base64 encoded claim_token

    Returns:
        str: The validated access URL - (or throws an error)

    Raises:
        SimpleFinInvalidAccountURLError: If the input string is an invalid access URL.
        SimpleFinPaymentRequiredError
        SimpleFinAuthError
        SimpleFinInvalidClaimTokenError: If the input string is an invalid claim token.
        SimpleFinClaimError: If there's an error in claim token processing.

    """

    if not input_string.startswith("http"):
        LOGGER.info("[Setup Token] - Claiming Access URL")
        access_url = await SimpleFin.claim_setup_token(input_string)

    else:
        LOGGER.info("[Access Url] - 'http' string detected")
        access_url = input_string
        LOGGER.info("[Access Url] - validating access url")
        SimpleFin.decode_access_url(access_url)

    LOGGER.info("[Access Url] - Fetching data")
    simple_fin = SimpleFin(access_url=access_url)
    await simple_fin.fetch_data()
    return access_url


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the initial setup of a SimpleFIN integration."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user for SimpleFIN API credentials."""
        errors = {}

        if user_input is not None:
            try:
                user_input[CONF_API_TOKEN] = await _validate_or_obtain_access_url(
                    user_input[CONF_API_TOKEN]
                )
            except SimpleFinInvalidAccountURLError:
                errors["base"] = "url_error"
            except SimpleFinInvalidClaimTokenError:
                errors["base"] = "invalid_claim_token"
            except SimpleFinClaimError:
                errors["base"] = "claim_error"
            except SimpleFinPaymentRequiredError:
                errors["base"] = "payment_required"
            except SimpleFinAuthError:
                errors["base"] = "auth_error"

            entry = await self.async_set_unique_id(user_input[CONF_API_TOKEN])
            if entry:
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            self._abort_if_unique_id_configured()

            if not errors:
                return self.async_create_entry(
                    title="SimpleFIN",
                    data={CONF_ACCESS_URL: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauth just re-triggers user step."""
        return await self.async_step_user()

"""Config flow for SimpleFIN integration."""

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
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult

from .const import CONF_ACCESS_URL, DOMAIN, LOGGER


async def _async_validate_or_obtain_access_url(input_string: str) -> str:
    """Validate the input string as an access URL or a claim token and fetch data using SimpleFin.

    A claim token will be a hex string
    An access URL will be an http/https url
    """

    if not input_string.startswith("http"):
        # Claim token detected - convert to an access url
        LOGGER.debug("[Setup Token] - Claiming Access URL")
        access_url = await SimpleFin.claim_setup_token(input_string)

    else:
        LOGGER.debug("[Access Url] - 'http' string detected")
        access_url = input_string
        LOGGER.debug("[Access Url] - validating access url")
        SimpleFin.decode_access_url(access_url)

    LOGGER.debug("[Access Url] - Fetching data")
    simple_fin = SimpleFin(access_url=access_url)
    await simple_fin.fetch_data()
    return access_url


class SimpleFinConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the initial setup of a SimpleFIN integration."""

    def __init__(self) -> None:
        """Initialize."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user for SimpleFIN API credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user_input[
                    CONF_ACCESS_URL
                ] = await _async_validate_or_obtain_access_url(
                    user_input[CONF_ACCESS_URL]
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="SimpleFIN",
                    data={CONF_ACCESS_URL: user_input[CONF_ACCESS_URL]},
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

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_URL): str,
                }
            ),
            errors=errors,
        )

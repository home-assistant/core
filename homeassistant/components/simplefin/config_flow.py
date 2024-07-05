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
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult

from .const import CONF_ACCESS_URL, DOMAIN, LOGGER

SF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_URL): str,
    }
)


async def __validate_or_obtain_access_url(input_string: str) -> str:
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


async def _validate_and_get_errors(
    user_input: dict[str, Any],
) -> tuple[str, dict[str, str]]:
    """Validate the user input and returns the validated URL and any errors that might occur."""

    errors = {}
    try:
        user_input[CONF_ACCESS_URL] = await __validate_or_obtain_access_url(
            user_input[CONF_ACCESS_URL]
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

    return user_input[CONF_ACCESS_URL], errors


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
            url, errors = await _validate_and_get_errors(user_input)
            user_input[CONF_ACCESS_URL] = url

            self._abort_if_unique_id_configured()

            if not errors:
                return self.async_create_entry(
                    title="SimpleFIN",
                    data={CONF_ACCESS_URL: user_input[CONF_ACCESS_URL]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=SF_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and confirm the reauth."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm", data_schema=SF_SCHEMA)

        assert self._reauth_entry

        url, errors = await _validate_and_get_errors(user_input)

        if errors:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=SF_SCHEMA, errors=errors
            )

        self.hass.config_entries.async_update_entry(
            self._reauth_entry, data=self._reauth_entry.data | user_input
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
        )
        return self.async_abort(reason="reauth_successful")

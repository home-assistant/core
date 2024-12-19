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

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult

from .const import CONF_ACCESS_URL, DOMAIN, LOGGER

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_URL): str,
    }
)


async def _validate_input(user_input: dict[str, Any]) -> tuple[str, dict[str, str]]:
    errors: dict[str, str] = {}

    # Validate Access URL and/or Claim token - converting to an Access URL
    access_url: str = user_input[CONF_ACCESS_URL]
    try:
        if not access_url.startswith("http"):
            # Claim token detected - convert to access url
            LOGGER.debug("[Setup Token] - Claiming Access URL")
            access_url = await SimpleFin.claim_setup_token(access_url)
        else:
            LOGGER.debug("[Access Url] - 'http' string detected")
            # Decode the access URL
            LOGGER.debug("[Access Url] - validating access url")
            SimpleFin.decode_access_url(access_url)

        # Check access_url is accessible
        LOGGER.debug("[Access Url] - Fetching data")
        simple_fin = SimpleFin(access_url=access_url)
        await simple_fin.fetch_data()

    except SimpleFinInvalidAccountURLError:
        errors["base"] = "url_error"
    except SimpleFinInvalidClaimTokenError:
        errors["base"] = "invalid_claim_token"
    except SimpleFinClaimError:
        errors["base"] = "claim_error"
    except SimpleFinPaymentRequiredError:
        errors["base"] = "payment_required"
    except SimpleFinAuthError:
        errors["base"] = "invalid_auth"

    return access_url, errors


class SimpleFinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the initial setup of a SimpleFIN integration."""

    reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user for SimpleFIN API credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            access_url, errors = await _validate_input(user_input)
            self._async_abort_entries_match({CONF_ACCESS_URL: access_url})

            if not errors:
                # create entry
                user_input[CONF_ACCESS_URL] = access_url

                return self.async_create_entry(
                    title="SimpleFIN",
                    data={CONF_ACCESS_URL: user_input[CONF_ACCESS_URL]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            access_url, errors = await _validate_input(user_input)
            if not errors and self.reauth_entry:
                return self.async_update_reload_and_abort(
                    self.reauth_entry,
                    data={CONF_ACCESS_URL: user_input[CONF_ACCESS_URL]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=SCHEMA,
        )

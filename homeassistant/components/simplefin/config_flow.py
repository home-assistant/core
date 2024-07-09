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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_ACCESS_URL, DOMAIN, LOGGER


class SimpleFinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the initial setup of a SimpleFIN integration."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user for SimpleFIN API credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            access_url: str = user_input[CONF_ACCESS_URL]
            self._async_abort_entries_match({CONF_ACCESS_URL: access_url})

            try:
                if not access_url.startswith("http"):
                    # Claim token detected - convert to access url
                    LOGGER.debug("[Setup Token] - Claiming Access URL")
                    access_url = await SimpleFin.claim_setup_token(access_url)
                else:
                    LOGGER.debug("[Access Url] - 'http' string detected")
                    # Validate the access URL
                    LOGGER.debug("[Access Url] - validating access url")
                    SimpleFin.decode_access_url(access_url)

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
            else:
                # We passed validation
                user_input[CONF_ACCESS_URL] = access_url

                return self.async_create_entry(
                    title="SimpleFIN",
                    data={CONF_ACCESS_URL: user_input[CONF_ACCESS_URL]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_URL): str,
                }
            ),
            errors=errors,
        )

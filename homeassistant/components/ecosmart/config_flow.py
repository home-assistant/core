"""Config flow for the ecosmart integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aioecosmart import (
    EcosmartAuthError,
    EcosmartClient,
    EcosmartConnectionError,
    EcosmartRateLimitError,
    Identity,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_TITLE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class EcosmartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ecosmart."""

    VERSION = 1

    async def _async_check_key(
        self, api_key: str, errors: dict[str, str]
    ) -> Identity | None:
        """Check a key and set the unique ID from the account it belongs to."""
        client = EcosmartClient(api_key, async_get_clientsession(self.hass))
        try:
            identity = await client.me()
        except EcosmartAuthError:
            errors["base"] = "invalid_auth"
        except EcosmartRateLimitError:
            # Expected: the key is simply out of budget for the moment.
            errors["base"] = "rate_limited"
        except EcosmartConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if not identity.allowed_icps:
                # A key can legitimately exist before switch-in completes.
                # There is nothing to poll for until an ICP appears.
                errors["base"] = "no_icps"
                return None
            # The account reference survives key rotation; the key
            # prefix does not, so it would make a poor unique ID.
            await self.async_set_unique_id(identity.account_ref)
            return identity
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an API key and check it before creating the entry."""
        errors: dict[str, str] = {}
        if user_input is not None and (
            identity := await self._async_check_key(user_input[CONF_API_KEY], errors)
        ):
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=identity.label or DEFAULT_TITLE, data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after the API rejected the key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key for the same account."""
        errors: dict[str, str] = {}
        if user_input is not None and await self._async_check_key(
            user_input[CONF_API_KEY], errors
        ):
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=user_input
            )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

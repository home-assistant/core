"""Config flow for the ecosmart integration."""

import logging
from typing import Any, override

from aioecosmart import (
    EcosmartAuthError,
    EcosmartClient,
    EcosmartConnectionError,
    EcosmartRateLimitError,
)
import voluptuous as vol

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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class EcosmartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ecosmart."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an API key and check it before creating the entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = EcosmartClient(
                user_input[CONF_API_KEY], async_get_clientsession(self.hass)
            )
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
                else:
                    # The account reference survives key rotation; the key
                    # prefix does not, so it would make a poor unique ID.
                    await self.async_set_unique_id(identity.account_ref)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=identity.label or DEFAULT_TITLE, data=user_input
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

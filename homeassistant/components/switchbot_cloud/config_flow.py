"""Config flow for SwitchBot via API integration."""

from logging import getLogger
import re
from typing import Any

from switchbot_api import (
    SwitchBotAPI,
    SwitchBotAuthenticationError,
    SwitchBotConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN

from .const import CONF_WEBHOOK_DOMAIN, DOMAIN, ENTRY_TITLE, WEBHOOK_DOMAIN_PATTERN

_LOGGER = getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_WEBHOOK_DOMAIN): str,
    }
)


def _validate_webhook_domain(domain: str) -> None:
    """Validate webhook domain."""
    if not re.match(WEBHOOK_DOMAIN_PATTERN, domain, re.IGNORECASE):
        raise ValueError("Webhook Domain Error")


class SwitchBotCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBot via API."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await SwitchBotAPI(
                    token=user_input[CONF_API_TOKEN], secret=user_input[CONF_API_KEY]
                ).list_devices()
                if user_input.get(CONF_WEBHOOK_DOMAIN):
                    _validate_webhook_domain(user_input[CONF_WEBHOOK_DOMAIN])
            except SwitchBotConnectionError:
                errors["base"] = "cannot_connect"
            except SwitchBotAuthenticationError:
                errors["base"] = "invalid_auth"
            except ValueError:
                errors["base"] = "webhook_domain_error"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_API_TOKEN], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=ENTRY_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

import voluptuous as vol

from anki.errors import SyncError

from .const import DEFAULT_HOST, DOMAIN
from .coordinator import AnkiDataUpdateCoordinator


logger = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]):
    """Validate the user input allows us to connect."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data[CONF_USERNAME] == data[CONF_USERNAME]
            and entry.data[CONF_HOST] == data[CONF_HOST]
        ):
            raise AlreadyConfigured
    coordinator = AnkiDataUpdateCoordinator(hass, data)
    coordinator.sync()
    return {
        "title": data[CONF_USERNAME]
        + (" on " + data[CONF_HOST] if data[CONF_HOST] != DEFAULT_HOST else ""),
    }


class AnkiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AnkiOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except SyncError:
                errors["base"] = "auth_failed"
            except Exception:
                logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class AnkiOptionsFlowHandler(OptionsFlow):
    """Handle Anki options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except SyncError:
                errors["base"] = "auth_failed"
            except Exception:
                logger.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class AlreadyConfigured(HomeAssistantError):
    """Error to indicate that the host is already configured."""

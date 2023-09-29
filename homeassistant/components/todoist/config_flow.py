"""Config flow for todoist integration."""

from http import HTTPStatus
import logging
from typing import Any

from requests.exceptions import HTTPError
from todoist_api_python.api_async import TodoistAPIAsync
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SETTINGS_URL = "https://todoist.com/app/settings/integrations"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for todoist."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            api = TodoistAPIAsync(user_input[CONF_TOKEN])
            try:
                await api.get_tasks()
            except HTTPError as err:
                if err.response.status_code == HTTPStatus.UNAUTHORIZED:
                    errors["base"] = "invalid_access_token"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Todoist", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"settings_url": SETTINGS_URL},
        )

"""Config flow for SwitchBot via API integration."""

from hashlib import sha256
from logging import getLogger
from typing import Any

from switchbot_api import CannotConnect, InvalidAuth, SwitchBotAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, ENTRY_TITLE

_LOGGER = getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    await SwitchBotAPI(
        token=data[CONF_API_TOKEN], secret=data[CONF_API_KEY]
    ).list_devices()
    return data


@config_entries.HANDLERS.register(DOMAIN)
class SwitchBotCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBot via API."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                unique_id = sha256(info[CONF_API_TOKEN].encode()).hexdigest()
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=ENTRY_TITLE, data=info)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

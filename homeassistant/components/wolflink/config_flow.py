"""Config flow for Wolf SmartSet Service integration."""

import logging

from httpx import RequestError
import voluptuous as vol
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import FetchFailed, WolfClient

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class WolfLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wolf SmartSet Service."""

    VERSION = 2
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step to get connection parameters."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            wolf_client = WolfClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            try:
                devices = await wolf_client.fetch_system_list()
            except RequestError, FetchFailed:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not devices:
                    return self.async_abort(reason="no_devices")
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        DEVICE_ID: [device.id for device in devices],
                    },
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

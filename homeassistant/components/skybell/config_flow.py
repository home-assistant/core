"""Config flow for Skybell integration."""
from requests.exceptions import ConnectTimeout, HTTPError
from skybellpy import Skybell, exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.typing import ConfigType

from . import _LOGGER
from .const import (  # pylint:disable=unused-import
    AGENT_IDENTIFIER,
    DEFAULT_CACHEDB,
    DOMAIN,
)


class SkybellFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Skybell."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(self, user_input: ConfigType):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            self._async_abort_entries_match({CONF_EMAIL: email})

            device_json, error = await self._async_try_connect(email, password)
            if error is None:
                await self.async_set_unique_id(device_json["user"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: password},
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=user_input.get(CONF_EMAIL)): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=user_input.get(CONF_PASSWORD),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_try_connect(self, email, password):
        try:
            skybell = await self.hass.async_add_executor_job(
                Skybell,
                email,
                password,
                True,
                False,
                self.hass.config.path(DEFAULT_CACHEDB),
                False,
                AGENT_IDENTIFIER,
                False,
            )
            devices = await self.hass.async_add_executor_job(skybell.get_devices)
            device_json = devices[0]._device_json
        except exceptions.SkybellAuthenticationException:
            _LOGGER.error("Authentication Error: please check credentials")
            return None, "invalid_auth"
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Cannot connect to SkyBell servers")
            return None, "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return None, "unknown"
        return device_json, None

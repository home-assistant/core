"""Config flow for Synology SRM integration."""
import logging

import requests
from synology_srm.http import SynologyError, SynologyHttpException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from . import fetch_srm_device_id, get_srm_client_from_user_data
from .const import DEFAULT_PORT, DEFAULT_SSL, DEFAULT_USERNAME, DEFAULT_VERIFY_SSL
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class SynologySrmFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Synology SRM."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                client = get_srm_client_from_user_data(user_input)
                device_id = await self.hass.async_add_executor_job(
                    fetch_srm_device_id, client
                )

                # Check if the device has already been configured
                await self.async_set_unique_id(device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=device_id, data=user_input)
            except (SynologyHttpException, requests.exceptions.ConnectionError) as ex:
                errors["base"] = "cannot_connect"
                _LOGGER.exception(ex)
            except SynologyError as error:
                if error.code >= 400:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
                _LOGGER.exception(error)
            except Exception as ex:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(ex)
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Optional(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Required(
                        CONF_USERNAME,
                        default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Optional(
                        CONF_SSL, default=user_input.get(CONF_SSL, DEFAULT_SSL)
                    ): bool,
                    vol.Optional(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    ): bool,
                }
            ),
            errors=errors,
        )

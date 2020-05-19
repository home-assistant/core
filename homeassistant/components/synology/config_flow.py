"""Config flow to configure the Synology DSM integration."""
from functools import partial
import logging

import requests
from synology.surveillance_station import SurveillanceStation
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from .const import DEFAULT_PORT, DEFAULT_SSL, DEFAULT_TIMEOUT, DEFAULT_VERITY_SSL
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class SynologyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            try:
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                ssl = user_input[CONF_SSL]
                verify_ssl = user_input[CONF_VERIFY_SSL]
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                timeout = user_input[CONF_TIMEOUT]

                protocol = "https" if ssl else "http"
                url = f"{protocol}://{host}:{port}"

                await self.hass.async_add_executor_job(
                    partial(
                        SurveillanceStation,
                        url,
                        username,
                        password,
                        verify_ssl=verify_ssl,
                        timeout=timeout,
                    )
                )

                return self.async_create_entry(
                    title="",
                    data={
                        CONF_URL: url,
                        CONF_VERIFY_SSL: verify_ssl,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_TIMEOUT: timeout,
                    },
                )
            except requests.exceptions.RequestException as err:
                _LOGGER.debug("Failed to connect to SurveillanceStation: %s", err)
                errors["base"] = "cannot_connect"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST) or ""
                    ): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT) or DEFAULT_PORT
                    ): str,
                    vol.Required(
                        CONF_SSL, default=user_input.get(CONF_SSL) or DEFAULT_SSL
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL) or DEFAULT_VERITY_SSL,
                    ): bool,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME) or ""
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD) or ""
                    ): str,
                    vol.Required(
                        CONF_TIMEOUT,
                        default=user_input.get(CONF_TIMEOUT) or DEFAULT_TIMEOUT,
                    ): int,
                }
            ),
            errors=errors,
        )

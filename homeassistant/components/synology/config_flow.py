"""Config flow to configure the Synology DSM integration."""
from functools import partial
import logging

import requests
from synology.surveillance_station import SurveillanceStation
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERITY_SSL,
)
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
        return await self.async_step_init(user_input)

    async def async_step_import(self, user_input=None):
        """Handle an import flow."""
        return await self.async_step_init(user_input, is_import=True)

    async def async_step_init(self, user_input=None, is_import=False):
        """Handle general flow first step."""
        errors = {}

        if user_input is not None:
            try:
                if is_import:
                    url = user_input[CONF_URL]
                else:
                    host = user_input[CONF_HOST]
                    port = user_input[CONF_PORT]
                    ssl = user_input[CONF_SSL]
                    protocol = "https" if ssl else "http"
                    url = f"{protocol}://{host}:{port}"

                if await self._async_url_already_configured(url):
                    return self.async_abort(reason="already_configured")

                name = user_input[CONF_NAME]
                verify_ssl = user_input[CONF_VERIFY_SSL]
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                timeout = user_input[CONF_TIMEOUT]

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
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_URL: url,
                        CONF_VERIFY_SSL: verify_ssl,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_TIMEOUT: timeout,
                    },
                )
            except requests.exceptions.RequestException as err:
                if is_import:
                    _LOGGER.exception("Failed to import: %s", err)
                    return self.async_abort(reason="cannot_connect")
                _LOGGER.debug("Failed to connect to SurveillanceStation: %s", err)
                errors["base"] = "cannot_connect"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME) or DEFAULT_NAME
                    ): str,
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

    async def _async_url_already_configured(self, url):
        """See if we already have a url matching user input."""
        existing_urls = [
            entry.data[CONF_URL] for entry in self._async_current_entries()
        ]
        return url in existing_urls

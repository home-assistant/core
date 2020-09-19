"""ZoneMinder config flow."""
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SOURCE,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from .common import (
    ClientAvailabilityResult,
    async_test_client_availability,
    create_client_from_config,
)
from .const import (
    CONF_PATH_ZMS,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
)
from .const import DOMAIN  # pylint: disable=unused-import


class ZoneminderFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Flow handler for zoneminder integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, config: dict):
        """Handle a flow initialized by import."""
        return await self.async_step_finish(
            {**config, **{CONF_SOURCE: config_entries.SOURCE_IMPORT}}
        )

    async def async_step_user(self, user_input: dict = None):
        """Handle user step."""
        user_input = user_input or {}
        errors = {}

        if user_input:
            zm_client = create_client_from_config(user_input)
            result = await async_test_client_availability(self.hass, zm_client)
            if result == ClientAvailabilityResult.AVAILABLE:
                return await self.async_step_finish(user_input)

            errors["base"] = result.value

        return self.async_show_form(
            step_id=config_entries.SOURCE_USER,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                    vol.Optional(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD)
                    ): str,
                    vol.Optional(
                        CONF_PATH, default=user_input.get(CONF_PATH, DEFAULT_PATH)
                    ): str,
                    vol.Optional(
                        CONF_PATH_ZMS,
                        default=user_input.get(CONF_PATH_ZMS, DEFAULT_PATH_ZMS),
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

    async def async_step_finish(self, config: dict):
        """Finish config flow."""
        zm_client = create_client_from_config(config)
        hostname = urlparse(zm_client.get_zms_url()).hostname
        result = await async_test_client_availability(self.hass, zm_client)

        if result != ClientAvailabilityResult.AVAILABLE:
            return self.async_abort(reason=str(result.value))

        await self.async_set_unique_id(hostname)
        self._abort_if_unique_id_configured(config)

        return self.async_create_entry(title=hostname, data=config)

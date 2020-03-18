"""Config flow to configure the Synology DSM integration."""
import logging

from SynologyDSM import SynologyDSM
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

from .const import (
    DEFAULT_DSM_VERSION,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_PORT_SSL,
    DEFAULT_SSL,
)
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class SynologyDSMFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Optional(CONF_PORT, default=user_input.get(CONF_PORT, "")): str,
                    vol.Optional(
                        CONF_SSL, default=user_input.get(CONF_SSL, DEFAULT_SSL)
                    ): bool,
                    vol.Optional(
                        CONF_API_VERSION,
                        default=user_input.get(CONF_API_VERSION, DEFAULT_DSM_VERSION),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.In([5, 6]),  # DSM versions supported by the library
                    ),
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form(user_input, None)

        name = user_input.get(CONF_NAME, DEFAULT_NAME)
        host = user_input[CONF_HOST]
        port = user_input.get(CONF_PORT)
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        use_ssl = user_input.get(CONF_SSL, DEFAULT_SSL)
        api_version = user_input.get(CONF_API_VERSION, DEFAULT_DSM_VERSION)

        if not port:
            if use_ssl is True:
                port = DEFAULT_PORT_SSL
            else:
                port = DEFAULT_PORT

        # Check if already configured
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        api = SynologyDSM(
            host, port, username, password, use_ssl, dsm_version=api_version,
        )

        if not await self.hass.async_add_executor_job(api.login):
            errors[CONF_USERNAME] = "login"
            return await self._show_setup_form(user_input, errors)

        storage = await self.hass.async_add_executor_job(getattr, api, "storage")
        utilisation = await self.hass.async_add_executor_job(
            getattr, api, "utilisation"
        )

        if (
            storage.volumes is None
            or storage.disks is None
            or utilisation.cpu_user_load is None
        ):
            errors["base"] = "unknown"
            return await self._show_setup_form(user_input, errors)

        return self.async_create_entry(
            title=host,
            data={
                CONF_NAME: name,
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_SSL: use_ssl,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
            },
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

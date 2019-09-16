"""Config flow to configure Livebox."""
import logging

from aiosysbus import Sysbus
from aiosysbus.exceptions import AuthorizationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback

from .const import (
    CONF_LAN_TRACKING,
    DEFAULT_HOST,
    DEFAULT_LAN_TRACKING,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    TEMPLATE_SENSOR,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class LiveboxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Livebox config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Livebox flow."""

        self._session = None
        self.host = None
        self.port = None
        self.username = None
        self.password = None
        self.box_id = None

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        errors = {}
        if user_input is not None:
            self.host = user_input["host"]
            self.port = user_input["port"]
            self.username = user_input["username"]
            self.password = user_input["password"]
            try:
                self._session = Sysbus(
                    username=self.username,
                    password=self.password,
                    host=self.host,
                    port=self.port,
                )

                perms = await self._session.async_get_permissions()
                if perms is not None:
                    return await self.async_step_register()

            except AuthorizationError:
                errors["base"] = "login_inccorect"

            except Exception as e:
                _LOGGER.warn("Error to connect {}".format(e))
                errors["base"] = "linking"

        # If there was no user input, do not show the errors.
        if user_input is None:
            errors = {}

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_register(self, user_input=None):
        """Step for register component."""

        errors = {}
        infos = await self._session.system.get_deviceinfo()
        self.box_id = infos.get("status").get("SerialNumber")
        entry_id = self.hass.config_entries.async_entries(DOMAIN)

        if self.box_id is not None:
            if entry_id and entry_id.get("data", {}).get("id", 0) == self.box_id:
                self.hass.config_entries.async_remove(entry_id)

            return self.async_create_entry(
                title=f"{TEMPLATE_SENSOR}",
                data={
                    "id": self.box_id,
                    "host": self.host,
                    "port": self.port,
                    "username": self.username,
                    "password": self.password,
                },
            )
        else:
            errors["base"] = "register_failed"

        return self.async_show_form(step_id="register", errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get option flow."""
        return LiveboxOptionsFlowHandler(config_entry)


class LiveboxOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle option."""

    def __init__(self, config_entry):
        """Initialize the options flow."""

        self.config_entry = config_entry
        self._lan_tracking = self.config_entry.options.get(
            CONF_LAN_TRACKING, DEFAULT_LAN_TRACKING
        )
        self.config_entry.add_update_listener(update_listener)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        OPTIONS_SCHEMA = vol.Schema(
            {vol.Required(CONF_LAN_TRACKING, default=self._lan_tracking): bool}
        )

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="user", data_schema=OPTIONS_SCHEMA)


async def update_listener(hass, config_entry):
    """Reload device tracker if change option."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "device_tracker")
    await hass.config_entries.async_forward_entry_setup(config_entry, "device_tracker")

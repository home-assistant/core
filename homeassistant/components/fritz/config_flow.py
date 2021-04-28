"""Config flow to configure the FRITZ!Box Tools integration."""
import logging
from urllib.parse import urlparse

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback

from .common import FritzBoxTools
from .const import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_AUTH_INVALID,
    ERROR_CONNECTION_ERROR,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class FritzBoxToolsFlowHandler(ConfigFlow):
    """Handle a FRITZ!Box Tools config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize FRITZ!Box Tools flow."""
        self._host = None
        self._entry = None
        self._name = None
        self._password = None
        self._port = None
        self._username = None
        self.import_schema = None
        self.fritz_tools = None

    async def fritz_tools_init(self):
        """Initialize FRITZ!Box Tools class."""
        self.fritz_tools = FritzBoxTools(
            hass=self.hass,
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
        )

        try:
            await self.fritz_tools.async_setup()
        except FritzSecurityError:
            return ERROR_AUTH_INVALID
        except FritzConnectionException:
            return ERROR_CONNECTION_ERROR
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return ERROR_UNKNOWN

        return None

    async def async_check_configured_entry(self) -> ConfigEntry:
        """Check if entry is configured."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] == self._host:
                return entry
        return None

    @callback
    def _async_create_entry(self):
        """Async create flow handler entry."""
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self.fritz_tools.host,
                CONF_PASSWORD: self.fritz_tools.password,
                CONF_PORT: self.fritz_tools.port,
                CONF_USERNAME: self.fritz_tools.username,
            },
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a flow initialized by discovery."""
        ssdp_location = urlparse(discovery_info[ATTR_SSDP_LOCATION])
        self._host = ssdp_location.hostname
        self._port = ssdp_location.port
        self._name = discovery_info.get(ATTR_UPNP_FRIENDLY_NAME)
        self.context[CONF_HOST] = self._host

        if uuid := discovery_info.get(ATTR_UPNP_UDN):
            if uuid.startswith("uuid:"):
                uuid = uuid[5:]
            await self.async_set_unique_id(uuid)
            self._abort_if_unique_id_configured({CONF_HOST: self._host})

        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self._host:
                return self.async_abort(reason="already_in_progress")

        if entry := await self.async_check_configured_entry():
            if uuid and not entry.unique_id:
                self.hass.config_entries.async_update_entry(entry, unique_id=uuid)
            return self.async_abort(reason="already_configured")

        self.context["title_placeholders"] = {
            "name": self._name.replace("FRITZ!Box ", "")
        }
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is None:
            return self._show_setup_form_confirm()

        errors = {}

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        error = await self.fritz_tools_init()

        if error:
            errors["base"] = error
            return self._show_setup_form_confirm(errors)

        return self._async_create_entry()

    def _show_setup_form_init(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors or {},
        )

    def _show_setup_form_confirm(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"name": self._name},
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form_init()
        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]
        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        if not (error := await self.fritz_tools_init()):
            self._name = self.fritz_tools.device_info["model"]

            if await self.async_check_configured_entry():
                error = "already_configured"

        if error:
            return self._show_setup_form_init({"base": error})

        return self._async_create_entry()

    async def async_step_reauth(self, data):
        """Handle flow upon an API authentication error."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._host = data[CONF_HOST]
        self._port = data[CONF_PORT]
        self._username = data[CONF_USERNAME]
        self._password = data[CONF_PASSWORD]
        return await self.async_step_reauth_confirm()

    def _show_setup_form_reauth_confirm(self, user_input, errors=None):
        """Show the reauth form to the user."""
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"host": self._host},
            errors=errors or {},
        )

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self._show_setup_form_reauth_confirm(
                user_input={CONF_USERNAME: self._username}
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        if error := await self.fritz_tools_init():
            return self._show_setup_form_reauth_confirm(
                user_input=user_input, errors={"base": error}
            )

        self.hass.config_entries.async_update_entry(
            self._entry,
            data={
                CONF_HOST: self._host,
                CONF_PASSWORD: self._password,
                CONF_PORT: self._port,
                CONF_USERNAME: self._username,
            },
        )
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(
            {
                CONF_HOST: import_config[CONF_HOST],
                CONF_USERNAME: import_config[CONF_USERNAME],
                CONF_PASSWORD: import_config.get(CONF_PASSWORD),
                CONF_PORT: import_config.get(CONF_PORT, DEFAULT_PORT),
            }
        )

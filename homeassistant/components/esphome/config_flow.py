"""Config flow to configure esphome component."""
from collections import OrderedDict
from typing import Optional

from aioesphomeapi import APIClient, APIConnectionError
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_PUSH, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entry_data import DATA_KEY, RuntimeEntryData

DOMAIN = "esphome"


class EsphomeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a esphome config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize flow."""
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self._password: Optional[str] = None

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None, error: Optional[str] = None
    ):  # pylint: disable=arguments-differ
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return await self._async_authenticate_or_add(user_input)

        fields = OrderedDict()
        fields[vol.Required(CONF_HOST, default=self._host or vol.UNDEFINED)] = str
        fields[vol.Optional(CONF_PORT, default=self._port or 6053)] = int

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    @property
    def _name(self):
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        return self.context.get(CONF_NAME)

    @_name.setter
    def _name(self, value):
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context[CONF_NAME] = value
        self.context["title_placeholders"] = {"name": self._name}

    def _set_user_input(self, user_input):
        if user_input is None:
            return
        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]

    async def _async_authenticate_or_add(self, user_input):
        self._set_user_input(user_input)
        error, device_info = await self.fetch_device_info()
        if error is not None:
            return await self.async_step_user(error=error)
        self._name = device_info.name

        # Only show authentication step if device uses password
        if device_info.uses_password:
            return await self.async_step_authenticate()

        return self._async_get_entry()

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self._async_authenticate_or_add(None)
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name}
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        # Hostname is format: livingroom.local.
        local_name = discovery_info["hostname"][:-1]
        node_name = local_name[: -len(".local")]
        address = discovery_info["properties"].get("address", local_name)

        # Check if already configured
        await self.async_set_unique_id(node_name)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info[CONF_HOST]}
        )

        for entry in self._async_current_entries():
            already_configured = False

            if (
                entry.data[CONF_HOST] == address
                or entry.data[CONF_HOST] == discovery_info[CONF_HOST]
            ):
                # Is this address or IP address already configured?
                already_configured = True
            elif entry.entry_id in self.hass.data.get(DATA_KEY, {}):
                # Does a config entry with this name already exist?
                data: RuntimeEntryData = self.hass.data[DATA_KEY][entry.entry_id]

                # Node names are unique in the network
                if data.device_info is not None:
                    already_configured = data.device_info.name == node_name

            if already_configured:
                # Backwards compat, we update old entries
                if not entry.unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_HOST: discovery_info[CONF_HOST]},
                        unique_id=node_name,
                    )

                return self.async_abort(reason="already_configured")

        self._host = discovery_info[CONF_HOST]
        self._port = discovery_info[CONF_PORT]
        self._name = node_name

        return await self.async_step_discovery_confirm()

    @callback
    def _async_get_entry(self):
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                # The API uses protobuf, so empty string denotes absence
                CONF_PASSWORD: self._password or "",
            },
        )

    async def async_step_authenticate(self, user_input=None, error=None):
        """Handle getting password for authentication."""
        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            error = await self.try_login()
            if error:
                return await self.async_step_authenticate(error=error)
            return self._async_get_entry()

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="authenticate",
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"name": self._name},
            errors=errors,
        )

    async def fetch_device_info(self):
        """Fetch device info from API and return any errors."""
        cli = APIClient(self.hass.loop, self._host, self._port, "")

        try:
            await cli.connect()
            device_info = await cli.device_info()
        except APIConnectionError as err:
            if "resolving" in str(err):
                return "resolve_error", None
            return "connection_error", None
        finally:
            await cli.disconnect(force=True)

        return None, device_info

    async def try_login(self):
        """Try logging in to device and return any errors."""
        cli = APIClient(self.hass.loop, self._host, self._port, self._password)

        try:
            await cli.connect(login=True)
        except APIConnectionError:
            await cli.disconnect(force=True)
            return "invalid_password"

        return None

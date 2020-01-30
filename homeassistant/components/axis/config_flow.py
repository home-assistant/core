"""Config flow to configure Axis devices."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from .const import CONF_MODEL, DOMAIN
from .device import get_device
from .errors import AuthenticationRequired, CannotConnect

AXIS_OUI = {"00408C", "ACCC8E", "B8A44F"}

CONFIG_FILE = "axis.conf"

EVENT_TYPES = ["motion", "vmd3", "pir", "sound", "daynight", "tampering", "input"]

PLATFORMS = ["camera"]

AXIS_INCLUDE = EVENT_TYPES + PLATFORMS

DEFAULT_PORT = 80


class AxisFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Axis config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Axis config flow."""
        self.device_config = {}
        self.model = None
        self.name = None
        self.serial_number = None

        self.discovery_schema = {}
        self.import_schema = {}

    async def async_step_user(self, user_input=None):
        """Handle a Axis config flow start.

        Manage device specific parameters.
        """
        errors = {}

        if user_input is not None:
            try:
                self.device_config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                device = await get_device(self.hass, self.device_config)

                self.serial_number = device.vapix.params.system_serialnumber
                config_entry = await self.async_set_unique_id(self.serial_number)
                if config_entry:
                    return self._update_entry(
                        config_entry,
                        host=user_input[CONF_HOST],
                        port=user_input[CONF_PORT],
                    )

                self.model = device.vapix.params.prodnbr

                return await self._create_entry()

            except AuthenticationRequired:
                errors["base"] = "faulty_credentials"

            except CannotConnect:
                errors["base"] = "device_unavailable"

        data = self.discovery_schema or {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user",
            description_placeholders=self.device_config,
            data_schema=vol.Schema(data),
            errors=errors,
        )

    async def _create_entry(self):
        """Create entry for device.

        Generate a name to be used as a prefix for device entities.
        """
        same_model = [
            entry.data[CONF_NAME]
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data[CONF_MODEL] == self.model
        ]

        self.name = f"{self.model}"
        for idx in range(len(same_model) + 1):
            self.name = f"{self.model} {idx}"
            if self.name not in same_model:
                break

        data = {
            CONF_DEVICE: self.device_config,
            CONF_NAME: self.name,
            CONF_MAC: self.serial_number,
            CONF_MODEL: self.model,
        }

        title = f"{self.model} - {self.serial_number}"
        return self.async_create_entry(title=title, data=data)

    def _update_entry(self, entry, host, port):
        """Update existing entry."""
        if (
            entry.data[CONF_DEVICE][CONF_HOST] == host
            and entry.data[CONF_DEVICE][CONF_PORT] == port
        ):
            return self.async_abort(reason="already_configured")

        entry.data[CONF_DEVICE][CONF_HOST] = host
        entry.data[CONF_DEVICE][CONF_PORT] = port

        self.hass.config_entries.async_update_entry(entry)
        return self.async_abort(reason="updated_configuration")

    async def async_step_zeroconf(self, discovery_info):
        """Prepare configuration for a discovered Axis device."""
        serial_number = discovery_info["properties"]["macaddress"]

        if serial_number[:6] not in AXIS_OUI:
            return self.async_abort(reason="not_axis_device")

        if discovery_info[CONF_HOST].startswith("169.254"):
            return self.async_abort(reason="link_local_address")

        config_entry = await self.async_set_unique_id(serial_number)
        if config_entry:
            return self._update_entry(
                config_entry,
                host=discovery_info[CONF_HOST],
                port=discovery_info[CONF_PORT],
            )

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            "name": discovery_info["hostname"][:-7],
            "host": discovery_info[CONF_HOST],
        }

        self.discovery_schema = {
            vol.Required(CONF_HOST, default=discovery_info[CONF_HOST]): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=discovery_info[CONF_PORT]): int,
        }

        return await self.async_step_user()

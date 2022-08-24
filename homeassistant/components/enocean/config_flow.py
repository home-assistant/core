"""Config flows for the ENOcean integration."""

import logging

from enocean.utils import from_hex_string, to_hex_string
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_DEVICE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import dongle
from .const import DOMAIN, ERROR_INVALID_DONGLE_PATH, LOGGER

_LOGGER = logging.getLogger(__name__)

CONF_ENOCEAN_DEVICES = "devices"
CONF_ENOCEAN_DEVICE_ID = "id"
CONF_ENOCEAN_DEVICE_NAME = "name"
CONF_ENOCEAN_SENDER_ID = "sender_id"
CONF_ENOCEAN_DEVICE_CLASS = "device_class"
CONF_ENOCEAN_MIN_TEMP = "min_temp"
CONF_ENOCEAN_MAX_TEMP = "max_temp"

MOCKUP_DEVICES = [
    selector.SelectOptionDict(value="12:34:56:78", label="Switch 1"),
    selector.SelectOptionDict(value="12:53:14:78", label="Switch 2"),
    selector.SelectOptionDict(value="12:53:56:78", label="Switch 3"),
    selector.SelectOptionDict(value="11:22:33:44", label="Light 1"),
    selector.SelectOptionDict(value="AB:CE:DE:F0", label="Light 2"),
    selector.SelectOptionDict(value="AB:CE:DE:F1", label="Light 3"),
]

MOCKUP_SENDER_IDS = [
    selector.SelectOptionDict(value="5E:53:AB:92", label="Chip ID (5E:53:AB:92)"),
    selector.SelectOptionDict(value="FF:FF:46:80", label="Base ID (FF:FF:46:80)"),
    selector.SelectOptionDict(value="FF:FF:46:81", label="Base ID + 1 (FF:FF:46:81)"),
    selector.SelectOptionDict(value="FF:FF:46:82", label="Base ID + 2 (FF:FF:46:82)"),
    selector.SelectOptionDict(value="FF:FF:46:83", label="Base ID + 3 (FF:FF:46:83)"),
]


ADD_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_ENOCEAN_DEVICE_ID, default="00:00:00:00"
        ): selector.SelectSelector(
            # For now, the list of devices will always be empty. For a
            # later version, it shall be pre-filled with all those
            # devices, from which the dongle has received telegrams.
            # (FUTURE WORK)
            # Hence the use of a SelectSelector.
            selector.SelectSelectorConfig(options=[], custom_value=True)
        ),
        vol.Optional(CONF_ENOCEAN_DEVICE_NAME, default=""): str,
        vol.Optional(CONF_ENOCEAN_SENDER_ID, default=""): str,
        vol.Optional(CONF_ENOCEAN_DEVICE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    "BinarySensorDeviceClass." + dc.name
                    for dc in BinarySensorDeviceClass
                ]
                + ["SensorDeviceClass." + dc.name for dc in SensorDeviceClass]
            )
        ),
    }
)

ADD_DEVICE_SCHEMA_ADVANCED_OPTIONS = {
    vol.Optional("channel", default=0): int,
    vol.Optional("min_temp", default=0): int,
    vol.Optional("max_temp", default=40): int,
    vol.Optional("range_from", default=255): int,
    vol.Optional("range_to", default=0): int,
}


class EnOceanFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the enOcean config flows."""

    VERSION = 1
    MANUAL_PATH_VALUE = "Custom path"

    def __init__(self) -> None:
        """Initialize the EnOcean config flow."""
        self.dongle_path = None
        self.discovery_info = None

    async def async_step_import(self, data=None):
        """Import a yaml configuration."""

        if not await self.validate_enocean_conf(data):
            LOGGER.warning(
                "Cannot import yaml configuration: %s is not a valid dongle path",
                data[CONF_DEVICE],
            )
            return self.async_abort(reason="invalid_dongle_path")

        return self.create_enocean_entry(data)

    async def async_step_user(self, user_input=None):
        """Handle an EnOcean config flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_detect()

    async def async_step_detect(self, user_input=None):
        """Propose a list of detected dongles."""
        errors = {}
        if user_input is not None:
            if user_input[CONF_DEVICE] == self.MANUAL_PATH_VALUE:
                return await self.async_step_manual(None)
            if await self.validate_enocean_conf(user_input):
                return self.create_enocean_entry(user_input)
            errors = {CONF_DEVICE: ERROR_INVALID_DONGLE_PATH}

        bridges = await self.hass.async_add_executor_job(dongle.detect)
        if len(bridges) == 0:
            return await self.async_step_manual(user_input)

        bridges.append(self.MANUAL_PATH_VALUE)
        return self.async_show_form(
            step_id="detect",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(bridges)}),
            errors=errors,
        )

    async def async_step_manual(self, user_input=None):
        """Request manual USB dongle path."""
        default_value = None
        errors = {}
        if user_input is not None:
            if await self.validate_enocean_conf(user_input):
                return self.create_enocean_entry(user_input)
            default_value = user_input[CONF_DEVICE]
            errors = {CONF_DEVICE: ERROR_INVALID_DONGLE_PATH}

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE, default=default_value): str}
            ),
            errors=errors,
        )

    async def validate_enocean_conf(self, user_input) -> bool:
        """Return True if the user_input contains a valid dongle path."""
        dongle_path = user_input[CONF_DEVICE]
        path_is_valid = await self.hass.async_add_executor_job(
            dongle.validate_path, dongle_path
        )
        return path_is_valid

    def create_enocean_entry(self, user_input):
        """Create an entry for the provided configuration."""
        return self.async_create_entry(title="EnOcean", data=user_input)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an option flow for EnOcean."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = config_entry.options

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            command = user_input["command"]
            if command == "manage_devices":
                return await self.async_step_manage_devices()

            if command == "add_device":
                return await self.async_step_add_device()

            return self.async_create_entry(title="", data=user_input)

        return self.async_show_menu(
            step_id="init",
            menu_options={
                "manage_devices": "Manage configured devices",
                "add_device": "Add new device",
            },
        )

    async def async_step_add_device(self, user_input=None) -> FlowResult:
        """Add an EnOcean device."""
        if user_input is not None:
            # validate input (not yet finished)
            # e.g. to check that device_id is indeed a valid id

            device_id = from_hex_string(user_input["id"])
            _LOGGER.debug(device_id)

            device_name = user_input["name"].strip()
            if device_name == "":
                device_name = "EnOcean device " + to_hex_string(device_id)

        device_schema = ADD_DEVICE_SCHEMA

        if self.show_advanced_options:
            device_schema.extend(ADD_DEVICE_SCHEMA_ADVANCED_OPTIONS)

        return self.async_show_form(
            step_id="add_device",
            data_schema=device_schema,
        )

    async def async_step_manage_devices(self, user_input=None) -> FlowResult:
        """Manage the configured EnOcean devices."""
        devices = self.options.get("devices", [])

        if user_input is not None:
            devices.append(user_input)
            return self.async_create_entry(title="", data={"devices": devices})

        return self.async_show_form(
            step_id="manage_devices",
            data_schema=ADD_DEVICE_SCHEMA,
        )

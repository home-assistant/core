"""Config flows for the EnOcean integration."""

from copy import deepcopy
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import dongle
from .const import DOMAIN, ENOCEAN_EQUIPMENT_PROFILES, ERROR_INVALID_DONGLE_PATH, LOGGER

_LOGGER = logging.getLogger(__name__)

CONF_ENOCEAN_DEVICES = "devices"
CONF_ENOCEAN_DEVICE_ID = "id"
CONF_ENOCEAN_EQUIPMENT_PROFILE = "eep"
CONF_ENOCEAN_DEVICE_NAME = "name"
CONF_ENOCEAN_SENDER_ID = "sender_id"
CONF_ENOCEAN_DEVICE_CLASS = "device_class"
CONF_ENOCEAN_MIN_TEMP = "min_temp"
CONF_ENOCEAN_MAX_TEMP = "max_temp"

CONF_ENOCEAN_MANAGE_DEVICE_COMMANDS = "manage_device_command"
ENOCEAN_EDIT_DEVICE_COMMAND = "edit"
ENOCEAN_DELETE_DEVICE_COMMAND = "delete"


MOCKUP_DEVICES = [
    selector.SelectOptionDict(
        value="12:34:56:78", label="12:34:56:78 [last seen on YYYY-MM-DD HH:MM]"
    ),
    selector.SelectOptionDict(
        value="12:53:14:78", label="12:53:14:78 [last seen on YYYY-MM-DD HH:MM]"
    ),
    selector.SelectOptionDict(
        value="12:53:56:78", label="12:53:56:78 [last seen on YYYY-MM-DD HH:MM]"
    ),
    selector.SelectOptionDict(
        value="11:22:33:44", label="11:22:33:44 [last seen on YYYY-MM-DD HH:MM]"
    ),
    selector.SelectOptionDict(
        value="AB:CE:DE:F0", label="AB:CE:DE:F0 [last seen on YYYY-MM-DD HH:MM]"
    ),
    selector.SelectOptionDict(
        value="AB:CE:DE:F1", label="AB:CE:DE:F1 [last seen on YYYY-MM-DD HH:MM]"
    ),
]

ADD_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_ENOCEAN_EQUIPMENT_PROFILE, default=""
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=ENOCEAN_EQUIPMENT_PROFILES)
        ),
        vol.Required(
            CONF_ENOCEAN_DEVICE_ID, default="00:00:00:00"
        ): selector.SelectSelector(
            # For now, the list of devices will always be empty. For a
            # later version, it shall be pre-filled with all those
            # devices, from which the dongle has received telegrams.
            # (FUTURE WORK)
            # Hence the use of a SelectSelector.
            selector.SelectSelectorConfig(options=MOCKUP_DEVICES, custom_value=True)
        ),
        vol.Required(CONF_ENOCEAN_DEVICE_NAME, default=""): str,
        vol.Optional(CONF_ENOCEAN_SENDER_ID, default=""): selector.SelectSelector(
            # For now, the list of sender_ids will be empty. For a
            # later version, it shall be pre-filled with the dongles chip ID
            # and its base IDs. (FUTURE WORK, requires update of enocean lib)
            # Hence the use of a SelectSelector.
            selector.SelectSelectorConfig(options=[], custom_value=True)
        ),
    }
)


ENOCEAN_MANAGE_DEVICE_COMMANDS = [
    selector.SelectOptionDict(
        value=ENOCEAN_EDIT_DEVICE_COMMAND, label="Edit device settings"
    ),
    selector.SelectOptionDict(
        value=ENOCEAN_DELETE_DEVICE_COMMAND, label="Delete device"
    ),
]


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

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        devices = self.config_entry.options.get(CONF_ENOCEAN_DEVICES, [])

        if len(devices) == 0:
            return self.async_show_menu(
                step_id="init",
                menu_options={
                    "add_device": "Add new device",
                },
            )

        return self.async_show_menu(
            step_id="init",
            menu_options={
                "add_device": "Add new device",
                "select_device": "Edit configured device",
                "delete_device": "Delete configured device",
            },
        )

    async def async_step_add_device(self, user_input=None) -> FlowResult:
        """Add an EnOcean device."""
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))

        if user_input is not None:
            # validate input (not yet finished)
            # e.g. to check that device_id is indeed a valid id
            device_id = user_input[CONF_ENOCEAN_DEVICE_ID]
            eep = user_input[CONF_ENOCEAN_EQUIPMENT_PROFILE]
            sender_id = user_input[CONF_ENOCEAN_SENDER_ID]
            device_name = user_input[CONF_ENOCEAN_DEVICE_NAME].strip()
            if device_name == "":
                device_name = "EnOcean device " + device_id

            devices.append(
                {
                    CONF_ENOCEAN_DEVICE_ID: device_id,
                    CONF_ENOCEAN_EQUIPMENT_PROFILE: eep,
                    CONF_ENOCEAN_DEVICE_NAME: device_name,
                    CONF_ENOCEAN_SENDER_ID: sender_id,
                }
            )

            return self.async_create_entry(
                title="", data={CONF_ENOCEAN_DEVICES: devices}
            )

        return self.async_show_form(
            step_id="add_device",
            data_schema=ADD_DEVICE_SCHEMA,
        )

    async def async_step_select_device(self, user_input=None) -> FlowResult:
        """Select a configured EnOcean device."""

        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))
        device_list = [
            selector.SelectOptionDict(
                value=device["id"], label=device["name"] + " [" + device["id"] + "]"
            )
            for device in devices
        ]
        device_list.sort(key=lambda entry: entry["label"].lower())

        if user_input is not None:
            device_id = user_input[CONF_DEVICE]

            # find the device belonging to the device_id
            device = None
            for dev in devices:
                if dev["id"] == device_id:
                    device = dev
                    break

            return await self.async_step_edit_device(None, device)

        select_device_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default="none"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=device_list)
                )
            }
        )

        return self.async_show_form(
            step_id="select_device",
            data_schema=select_device_schema,
        )

    async def async_step_edit_device(self, user_input=None, device=None) -> FlowResult:
        """Edit an EnOcean device."""
        default_device_id = "none"
        if device is not None:
            default_device_id = device["id"]

        default_device_name = "none"
        if device is not None:
            default_device_name = device["name"]

        default_eep = "none"
        if device is not None:
            default_eep = device["eep"]

        default_sender_id = "none"
        if device is not None:
            default_sender_id = device["sender_id"]

        edit_device_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENOCEAN_DEVICE_ID, default=default_device_id
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=[default_device_id])
                ),
                vol.Required(
                    CONF_ENOCEAN_EQUIPMENT_PROFILE, default=default_eep
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=ENOCEAN_EQUIPMENT_PROFILES)
                ),
                vol.Required(
                    CONF_ENOCEAN_DEVICE_NAME, default=default_device_name
                ): str,
                vol.Optional(
                    CONF_ENOCEAN_SENDER_ID, default=default_sender_id
                ): selector.SelectSelector(
                    # For now, the list of sender_ids will be empty. For a
                    # later version, it shall be pre-filled with the dongle's
                    # chip ID and its base IDs. (FUTURE WORK, requires update
                    # of enocean lib).
                    # Hence the use of a SelectSelector.
                    selector.SelectSelectorConfig(options=[], custom_value=True)
                ),
            }
        )

        return self.async_show_form(
            step_id="edit_device",
            data_schema=edit_device_schema,
        )

    async def async_step_delete_device(self, user_input=None) -> FlowResult:
        """Delete an EnOcean device."""
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))
        device_list = [
            selector.SelectOptionDict(
                value=device["id"], label=device["name"] + " [" + device["id"] + "]"
            )
            for device in devices
        ]
        device_list.sort(key=lambda entry: entry["label"].lower())

        if user_input is not None:
            device_id = user_input[CONF_ENOCEAN_DEVICE_ID]

            # find the device belonging to the device_id
            device = None
            for dev in devices:
                if dev["id"] == device_id:
                    device = dev
                    break

            devices.remove(device)
            return self.async_create_entry(
                title="", data={CONF_ENOCEAN_DEVICES: devices}
            )

        delete_device_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENOCEAN_DEVICE_ID, default="none"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=device_list)
                ),
            }
        )

        return self.async_show_form(
            step_id="delete_device",
            data_schema=delete_device_schema,
        )

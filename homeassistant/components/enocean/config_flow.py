"""Config flows for the EnOcean integration."""

from copy import deepcopy
import logging

from enocean.utils import from_hex_string, to_hex_string
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import dongle
from .const import DOMAIN, ENOCEAN_SUPPORTED_DEVICES, ERROR_INVALID_DONGLE_PATH, LOGGER
from .enocean_supported_device_type import EnOceanSupportedDeviceType

_LOGGER = logging.getLogger(__name__)

CONF_ENOCEAN_DEVICES = "devices"
CONF_ENOCEAN_DEVICE_ID = "id"
CONF_ENOCEAN_EEP = "eep"
CONF_ENOCEAN_MANUFACTURER = "manufacturer"
CONF_ENOCEAN_MODEL = "model"
CONF_ENOCEAN_DEVICE_NAME = "name"
CONF_ENOCEAN_SENDER_ID = "sender_id"
CONF_ENOCEAN_MANAGE_DEVICE_COMMANDS = "manage_device_command"

# step ids
ENOCEAN_STEP_ID_INIT = "init"
ENOCEAN_STEP_ID_ADD_DEVICE = "add_device"
ENOCEAN_STEP_ID_SELECT_DEVICE = "select_device_to_edit"
ENOCEAN_STEP_ID_EDIT_DEVICE = "edit_device"
ENOCEAN_STEP_ID_DELETE_DEVICE = "delete_device"

# menu options
ENOCEAN_MENU_OPTION_ADD_DEVICE = "add_device"
ENOCEAN_MENU_OPTION_SELECT_DEVICE = "select_device_to_edit"
ENOCEAN_MENU_OPTION_DELETE_DEVICE = "delete_device"

# errors
ENOCEAN_ERROR_INVALID_DEVICE_ID = "invalid_device_id"
ENOCEAN_ERROR_INVALID_SENDER_ID = "invalid_sender_id"
ENOCEAN_ERROR_DEVICE_NAME_EMPTY = "device_name_empty"
ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED = "device_already_configured"

# others
ENOCEAN_DEVICE_DEFAULT_NAME = "EnOcean device"
ENOCEAN_DEVICE_TYPE = "device_type"


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
                step_id=ENOCEAN_STEP_ID_INIT,
                menu_options=[ENOCEAN_MENU_OPTION_ADD_DEVICE],
            )

        return self.async_show_menu(
            step_id=ENOCEAN_STEP_ID_INIT,
            menu_options=[
                ENOCEAN_MENU_OPTION_ADD_DEVICE,
                ENOCEAN_MENU_OPTION_SELECT_DEVICE,
                ENOCEAN_MENU_OPTION_DELETE_DEVICE,
            ],
        )

    async def async_step_add_device(self, user_input=None) -> FlowResult:
        """Add an EnOcean device."""
        errors: dict[str, str] = {}
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))

        add_device_schema = None

        default_device_type = ""
        default_device_id = "00:00:00:00"
        default_device_name = ""
        default_sender_id = ""

        if user_input is not None:
            device_id = user_input[CONF_ENOCEAN_DEVICE_ID].strip()
            if self.validate_enocean_id_string(device_id):
                device_id = self.normalize_enocean_id_string(device_id)

                for dev in devices:
                    if dev[CONF_ENOCEAN_DEVICE_ID] == device_id:
                        errors["base"] = ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED
            else:
                errors["base"] = ENOCEAN_ERROR_INVALID_DEVICE_ID

            device_type_id = user_input[ENOCEAN_DEVICE_TYPE]
            device_type = EnOceanSupportedDeviceType("", "", "")
            for esd in ENOCEAN_SUPPORTED_DEVICES:
                if esd.unique_id == device_type_id:
                    device_type = esd
                    break
            if device_type.unique_id == "":
                errors["base"] = "invalid_device_type"

            sender_id = user_input[CONF_ENOCEAN_SENDER_ID].strip()
            if sender_id != "":
                if self.validate_enocean_id_string(sender_id):
                    sender_id = self.normalize_enocean_id_string(sender_id)
                else:
                    errors["base"] = ENOCEAN_ERROR_INVALID_SENDER_ID

            device_name = user_input[CONF_ENOCEAN_DEVICE_NAME].strip()
            if device_name == "":
                errors["base"] = ENOCEAN_ERROR_DEVICE_NAME_EMPTY

            if not errors:
                devices.append(
                    {
                        CONF_ENOCEAN_DEVICE_ID: device_id,
                        CONF_ENOCEAN_EEP: device_type.eep,
                        CONF_ENOCEAN_MANUFACTURER: device_type.manufacturer,
                        CONF_ENOCEAN_MODEL: device_type.model,
                        CONF_ENOCEAN_DEVICE_NAME: device_name,
                        CONF_ENOCEAN_SENDER_ID: sender_id,
                    }
                )

                return self.async_create_entry(
                    title="", data={CONF_ENOCEAN_DEVICES: devices}
                )

        add_device_schema = vol.Schema(
            {
                vol.Required(
                    ENOCEAN_DEVICE_TYPE,
                    default=default_device_type,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            esd.select_option_dict for esd in ENOCEAN_SUPPORTED_DEVICES
                        ]
                    )
                ),
                vol.Required(
                    CONF_ENOCEAN_DEVICE_ID,
                    default=default_device_id,
                ): selector.SelectSelector(
                    # For now, the list of devices will be empty. For a
                    # later version, it shall be pre-filled with all those
                    # devices, from which the dongle has received telegrams.
                    # (FUTURE WORK)
                    # Hence the use of a SelectSelector.
                    selector.SelectSelectorConfig(options=[], custom_value=True)
                ),
                vol.Required(
                    CONF_ENOCEAN_DEVICE_NAME,
                    default=default_device_name,
                ): str,
                vol.Optional(
                    CONF_ENOCEAN_SENDER_ID,
                    default=default_sender_id,
                ): selector.SelectSelector(
                    # For now, the list of sender_ids will be empty. For a
                    # later version, it shall be pre-filled with the dongles # chip ID and its base IDs. (FUTURE WORK, requires update # of enocean lib)
                    # Hence the use of a SelectSelector.
                    selector.SelectSelectorConfig(options=[], custom_value=True)
                ),
            }
        )

        return self.async_show_form(
            step_id=ENOCEAN_STEP_ID_ADD_DEVICE,
            data_schema=add_device_schema,
            errors=errors,
        )

    async def async_step_select_device_to_edit(self, user_input=None) -> FlowResult:
        """Select a configured EnOcean device to edit."""

        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))
        device_list = [
            selector.SelectOptionDict(
                value=device[CONF_ENOCEAN_DEVICE_ID],
                label=device[CONF_ENOCEAN_DEVICE_NAME]
                + " ["
                + device[CONF_ENOCEAN_DEVICE_ID]
                + "]",
            )
            for device in devices
        ]
        device_list.sort(key=lambda entry: entry["label"].lower())

        if user_input is not None:
            device_id = user_input[CONF_DEVICE]

            # find the device belonging to the device_id
            device = None
            for dev in devices:
                if dev[CONF_ENOCEAN_DEVICE_ID] == device_id:
                    device = dev
                    break

            return await self.async_step_edit_device(None, device)

        select_device_to_edit_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default="none"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=device_list)
                )
            }
        )

        return self.async_show_form(
            step_id=ENOCEAN_STEP_ID_SELECT_DEVICE,
            data_schema=select_device_to_edit_schema,
        )

    async def async_step_edit_device(self, user_input=None, device=None) -> FlowResult:
        """Edit an EnOcean device."""
        errors: dict[str, str] = {}
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))

        default_device_id = "none"
        default_device_name = "none"
        default_device_type_id = "none"
        default_sender_id = "none"

        if device is not None:
            default_device_id = device[CONF_ENOCEAN_DEVICE_ID]
            default_device_name = device[CONF_ENOCEAN_DEVICE_NAME]
            default_device_type_id = EnOceanSupportedDeviceType(
                eep=device[CONF_ENOCEAN_EEP],
                manufacturer=device[CONF_ENOCEAN_MANUFACTURER],
                model=device[CONF_ENOCEAN_MODEL],
            ).unique_id
            default_sender_id = device[CONF_ENOCEAN_SENDER_ID]

        if user_input is not None:
            sender_id = user_input[CONF_ENOCEAN_SENDER_ID].strip()
            if sender_id != "":
                if self.validate_enocean_id_string(sender_id):
                    sender_id = self.normalize_enocean_id_string(sender_id)
                else:
                    errors["base"] = ENOCEAN_ERROR_INVALID_SENDER_ID

            device_type_id = user_input[ENOCEAN_DEVICE_TYPE]
            device_type = EnOceanSupportedDeviceType("", "", "")
            for esd in ENOCEAN_SUPPORTED_DEVICES:
                if esd.unique_id == device_type_id:
                    device_type = esd
                    break
            if device_type.unique_id == "":
                errors["base"] = "invalid_device_type"

            device_name = user_input[CONF_ENOCEAN_DEVICE_NAME].strip()
            if device_name == "":
                errors["base"] = ENOCEAN_ERROR_DEVICE_NAME_EMPTY

            if not errors:
                for dev in devices:
                    if (
                        dev[CONF_ENOCEAN_DEVICE_ID]
                        == user_input[CONF_ENOCEAN_DEVICE_ID]
                    ):
                        dev[CONF_ENOCEAN_EEP] = device_type.eep
                        dev[CONF_ENOCEAN_MANUFACTURER] = device_type.manufacturer
                        dev[CONF_ENOCEAN_MODEL] = device_type.model
                        dev[CONF_ENOCEAN_DEVICE_NAME] = device_name
                        dev[CONF_ENOCEAN_SENDER_ID] = sender_id

                return self.async_create_entry(
                    title="", data={CONF_ENOCEAN_DEVICES: devices}
                )

            default_device_id = user_input[CONF_ENOCEAN_DEVICE_ID]
            default_device_name = user_input[CONF_ENOCEAN_DEVICE_NAME]
            default_device_type_id = user_input[ENOCEAN_DEVICE_TYPE]
            default_sender_id = user_input[CONF_ENOCEAN_SENDER_ID]

        edit_device_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENOCEAN_DEVICE_ID, default=default_device_id
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=[default_device_id])
                ),
                vol.Required(
                    ENOCEAN_DEVICE_TYPE, default=default_device_type_id
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            esd.select_option_dict for esd in ENOCEAN_SUPPORTED_DEVICES
                        ]
                    )
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
            step_id=ENOCEAN_STEP_ID_EDIT_DEVICE,
            data_schema=edit_device_schema,
        )

    async def async_step_delete_device(self, user_input=None) -> FlowResult:
        """Delete an EnOcean device."""
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))
        device_list = [
            selector.SelectOptionDict(
                value=device[CONF_ENOCEAN_DEVICE_ID],
                label=device[CONF_ENOCEAN_DEVICE_NAME]
                + " ["
                + device[CONF_ENOCEAN_DEVICE_ID]
                + "]",
            )
            for device in devices
        ]
        device_list.sort(key=lambda entry: entry["label"].lower())

        if user_input is not None:
            device_id = user_input[CONF_ENOCEAN_DEVICE_ID]

            # find the device belonging to the device_id
            device = None
            for dev in devices:
                if dev[CONF_ENOCEAN_DEVICE_ID] == device_id:
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
            step_id=ENOCEAN_STEP_ID_DELETE_DEVICE,
            data_schema=delete_device_schema,
        )

    def validate_enocean_id_string(self, id_string: str) -> bool:
        """Check that the supplied string is a valid EnOcean id."""
        parts = id_string.split(":")

        if len(parts) < 3:
            return False
        try:
            for part in parts:
                if len(part) > 2:
                    return False

                if int(part, 16) > 255:
                    return False

        except ValueError:
            return False

        return True

    def normalize_enocean_id_string(self, id_string: str) -> str:
        """Normalize the supplied EnOcean ID string."""
        return to_hex_string(from_hex_string(id_string))

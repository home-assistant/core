"""Config flows for the EnOcean integration."""

from copy import deepcopy
from typing import Any

from enocean.utils import from_hex_string, to_hex_string
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_DEVICE
from homeassistant.core import callback
from homeassistant.helpers import selector

from . import dongle
from .const import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_NAME,
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    CONF_ENOCEAN_DEVICES,
    CONF_ENOCEAN_SENDER_ID,
    DATA_ENOCEAN,
    DOMAIN,
    ENOCEAN_DEFAULT_DEVICE_NAME,
    ENOCEAN_DEVICE_TYPE_ID,
    ENOCEAN_DONGLE,
    ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED,
    ENOCEAN_ERROR_DEVICE_NAME_EMPTY,
    ENOCEAN_ERROR_INVALID_DEVICE_ID,
    ENOCEAN_ERROR_INVALID_SENDER_ID,
    ENOCEAN_MENU_OPTION_ADD_DEVICE,
    ENOCEAN_MENU_OPTION_DELETE_DEVICE,
    ENOCEAN_MENU_OPTION_SELECT_DEVICE,
    ENOCEAN_STEP_ID_ADD_DEVICE,
    ENOCEAN_STEP_ID_DELETE_DEVICE,
    ENOCEAN_STEP_ID_EDIT_DEVICE,
    ENOCEAN_STEP_ID_INIT,
    ENOCEAN_STEP_ID_SELECT_DEVICE,
    ERROR_INVALID_DONGLE_PATH,
)
from .enocean_id import EnOceanID
from .supported_device_type import (
    EnOceanSupportedDeviceType,
    get_supported_enocean_device_types,
)


class EnOceanFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle the enOcean config flows."""

    VERSION = 1
    MANUAL_PATH_VALUE = "manual"

    def __init__(self) -> None:
        """Initialize the EnOcean config flow."""
        self.dongle_path = None
        self.discovery_info = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an EnOcean config flow start."""
        return await self.async_step_detect()

    async def async_step_detect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Propose a list of detected dongles."""
        errors = {}
        if user_input is not None:
            if user_input[CONF_DEVICE] == self.MANUAL_PATH_VALUE:
                return await self.async_step_manual()
            if await self.validate_enocean_conf(user_input):
                return self.create_enocean_entry(user_input)
            errors = {CONF_DEVICE: ERROR_INVALID_DONGLE_PATH}

        devices = await self.hass.async_add_executor_job(dongle.detect)
        if len(devices) == 0:
            return await self.async_step_manual(user_input)
        devices.append(self.MANUAL_PATH_VALUE)

        return self.async_show_form(
            step_id="detect",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=devices,
                            translation_key="devices",
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        return await self.hass.async_add_executor_job(dongle.validate_path, dongle_path)

    def create_enocean_entry(self, user_input):
        """Create an entry for the provided configuration."""
        return self.async_create_entry(title="EnOcean", data=user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle an option flow for EnOcean."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Show menu displaying the options."""
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

    async def async_step_add_device(self, user_input=None) -> ConfigFlowResult:
        """Add an EnOcean device."""
        errors: dict[str, str] = {}
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))

        add_device_schema = None

        default_device_type = ""
        default_device_id = ""
        default_device_name = ""
        default_sender_id = self.hass.data[DATA_ENOCEAN][
            ENOCEAN_DONGLE
        ].base_id.to_string()

        device_id: EnOceanID | None = None
        device_name: str | None = None
        sender_id: EnOceanID | None = None

        if user_input is not None:
            # device id must be a valid EnOcean ID and not already configured
            if not EnOceanID.validate_string(user_input[CONF_ENOCEAN_DEVICE_ID]):
                errors[CONF_ENOCEAN_DEVICE_ID] = ENOCEAN_ERROR_INVALID_DEVICE_ID

            else:
                device_id = EnOceanID(user_input[CONF_ENOCEAN_DEVICE_ID])

                for dev in devices:
                    if not EnOceanID.validate_string(dev[CONF_ENOCEAN_DEVICE_ID]):
                        continue
                    if (
                        EnOceanID(dev[CONF_ENOCEAN_DEVICE_ID]).to_number()
                        == device_id.to_number()
                    ):
                        errors[CONF_ENOCEAN_DEVICE_ID] = (
                            ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED
                        )
                        break

            device_type_id = user_input[ENOCEAN_DEVICE_TYPE_ID]
            device_type = get_supported_enocean_device_types()[device_type_id]

            # sender id must be a valid EnOceanID string
            if user_input[CONF_ENOCEAN_SENDER_ID].strip() == "":
                sender_id = self.hass.data[DATA_ENOCEAN][ENOCEAN_DONGLE].base_id
            elif not EnOceanID.validate_string(user_input[CONF_ENOCEAN_SENDER_ID]):
                errors[CONF_ENOCEAN_SENDER_ID] = ENOCEAN_ERROR_INVALID_SENDER_ID
            else:
                sender_id = EnOceanID(user_input[CONF_ENOCEAN_SENDER_ID])

            # if the device name was not set, use a default name
            device_name = user_input[CONF_ENOCEAN_DEVICE_NAME].strip()
            if device_name == "":
                device_name = ENOCEAN_DEFAULT_DEVICE_NAME + (
                    " " + device_id.to_string() if device_id else ""
                )

            # append to the configuration if no errors
            if not errors:
                assert device_id is not None
                assert sender_id is not None
                devices.append(
                    {
                        CONF_ENOCEAN_DEVICE_ID: device_id.to_string(),
                        CONF_ENOCEAN_DEVICE_TYPE_ID: device_type.unique_id,
                        CONF_ENOCEAN_DEVICE_NAME: device_name,
                        CONF_ENOCEAN_SENDER_ID: sender_id.to_string(),
                    }
                )

                return self.async_create_entry(
                    title="", data={CONF_ENOCEAN_DEVICES: devices}
                )

            default_device_type = device_type_id
            default_device_id = device_id.to_string() if device_id else ""
            default_device_name = device_name
            default_sender_id = sender_id.to_string() if sender_id else ""

        supported_devices = [
            esd.select_option_dict
            for esd in list(get_supported_enocean_device_types().values())
        ]
        supported_devices.sort(key=lambda entry: entry["label"].upper())

        add_device_schema = vol.Schema(
            {
                vol.Required(
                    ENOCEAN_DEVICE_TYPE_ID,
                    default=default_device_type,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=supported_devices)
                ),
                vol.Required(
                    CONF_ENOCEAN_DEVICE_ID, default=default_device_id
                ): selector.SelectSelector(
                    # For now, the list of devices will be empty. For a
                    # later version, it shall be pre-filled with all those
                    # devices, from which the dongle has received telegrams.
                    # (FUTURE WORK)
                    # Hence the use of a SelectSelector.
                    selector.SelectSelectorConfig(options=[], custom_value=True)
                ),
                vol.Optional(
                    CONF_ENOCEAN_DEVICE_NAME,
                    default=default_device_name,
                ): str,
                vol.Optional(
                    CONF_ENOCEAN_SENDER_ID,
                    default=default_sender_id,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self.hass.data[DATA_ENOCEAN][
                            ENOCEAN_DONGLE
                        ].valid_sender_ids(),
                        custom_value=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=ENOCEAN_STEP_ID_ADD_DEVICE,
            data_schema=add_device_schema,
            errors=errors,
        )

    async def async_step_select_device_to_edit(
        self, user_input=None
    ) -> ConfigFlowResult:
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
        device_list.sort(key=lambda entry: entry["label"].upper())

        if user_input is not None:
            device_id = user_input[CONF_ENOCEAN_DEVICE_ID]

            # find the device belonging to the device_id
            device = None
            for dev in devices:
                if dev[CONF_ENOCEAN_DEVICE_ID] == device_id:
                    device = dev
                    break

            return await self.async_step_edit_device(None, device)

        select_device_to_edit_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENOCEAN_DEVICE_ID, default="none"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=device_list)
                )
            }
        )

        return self.async_show_form(
            step_id=ENOCEAN_STEP_ID_SELECT_DEVICE,
            data_schema=select_device_to_edit_schema,
        )

    async def async_step_edit_device(
        self, user_input=None, device=None
    ) -> ConfigFlowResult:
        """Edit an EnOcean device."""
        errors: dict[str, str] = {}
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))

        device_id = "none"
        device_name = "none"
        device_type = EnOceanSupportedDeviceType()
        sender_id = ""

        if device is not None:  # user_input will be ignored in this case
            device_id = device[CONF_ENOCEAN_DEVICE_ID]
            device_name = device[CONF_ENOCEAN_DEVICE_NAME]
            device_type = get_supported_enocean_device_types()[
                device[CONF_ENOCEAN_DEVICE_TYPE_ID]
            ]
            sender_id = device[CONF_ENOCEAN_SENDER_ID]

        elif user_input is not None:
            # device id needs no validation as user cannot change it
            device_id = user_input[CONF_ENOCEAN_DEVICE_ID]

            # sender id must be either empty or a valid EnOcean ID
            sender_id = user_input[CONF_ENOCEAN_SENDER_ID].strip()
            if sender_id != "":
                if EnOceanID.validate_string(sender_id):
                    sender_id = self.normalize_enocean_id_string(sender_id)
                else:
                    errors[CONF_ENOCEAN_SENDER_ID] = ENOCEAN_ERROR_INVALID_SENDER_ID

            device_type_id = user_input[ENOCEAN_DEVICE_TYPE_ID]
            device_type = get_supported_enocean_device_types()[device_type_id]

            # device name must not be empty
            device_name = user_input[CONF_ENOCEAN_DEVICE_NAME].strip()
            if device_name == "":
                errors[CONF_ENOCEAN_DEVICE_NAME] = ENOCEAN_ERROR_DEVICE_NAME_EMPTY

            if not errors:
                for dev in devices:
                    if dev[CONF_ENOCEAN_DEVICE_ID] == device_id:
                        dev[CONF_ENOCEAN_DEVICE_TYPE_ID] = device_type.unique_id
                        dev[CONF_ENOCEAN_DEVICE_NAME] = device_name
                        dev[CONF_ENOCEAN_SENDER_ID] = sender_id
                        break

                return self.async_create_entry(
                    title="", data={CONF_ENOCEAN_DEVICES: devices}
                )

        supported_devices = [
            esd.select_option_dict
            for esd in list(get_supported_enocean_device_types().values())
        ]
        supported_devices.sort(key=lambda entry: entry["label"].upper())

        edit_device_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENOCEAN_DEVICE_ID, default=device_id
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=[device_id])
                ),
                vol.Required(
                    ENOCEAN_DEVICE_TYPE_ID, default=device_type.unique_id
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=supported_devices)
                ),
                vol.Required(CONF_ENOCEAN_DEVICE_NAME, default=device_name): str,
                vol.Optional(
                    CONF_ENOCEAN_SENDER_ID, default=sender_id
                ): selector.SelectSelector(
                    # For now, the list of sender_ids will be empty. For a
                    # later version, it shall be pre-filled with the dongle's
                    # chip ID and its base IDs. (FUTURE WORK, requires update
                    # of enocean lib).
                    # Hence the use of a SelectSelector.
                    selector.SelectSelectorConfig(
                        options=self.hass.data[DATA_ENOCEAN][
                            ENOCEAN_DONGLE
                        ].valid_sender_ids(),
                        custom_value=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=ENOCEAN_STEP_ID_EDIT_DEVICE,
            data_schema=edit_device_schema,
            errors=errors,
        )

    async def async_step_delete_device(self, user_input=None) -> ConfigFlowResult:
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
        device_list.sort(key=lambda entry: entry["label"].upper())

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

    def normalize_enocean_id_string(self, id_string: str) -> str:
        """Normalize the supplied EnOcean ID string."""
        return to_hex_string(from_hex_string(id_string)).upper()

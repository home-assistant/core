"""Config flows for the EnOcean integration."""

from copy import deepcopy
import glob
from typing import Any

from enocean_async import DEVICE_TYPES, DeviceType, Gateway
from enocean_async.address import (
    EURID as EnOceanDeviceAddress,
    Address as EnOceanAddress,
)
import voluptuous as vol

from homeassistant.components import usb
from homeassistant.components.usb import (
    human_readable_device_name,
    usb_unique_id_from_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import ATTR_MANUFACTURER, CONF_DEVICE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from . import EnOceanConfigEntry
from .const import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    CONF_ENOCEAN_DEVICES,
    CONF_ENOCEAN_SENDER_ID,
    DOMAIN,
    ENOCEAN_DEVICE_TYPE_ID,
    ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED,
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
    LOGGER,
    MANUFACTURER,
)

MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): cv.string,
    }
)


def _device_type_label(dt: DeviceType) -> str:
    """Return a human-readable label for a DeviceType."""
    if dt.manufacturer is not None:
        return f"{dt.manufacturer.display_name} {dt.model!s}"
    return str(dt.model)


def _detect_usb_dongle() -> list[str]:
    """Return a list of candidate paths for USB EnOcean dongles.

    This method is currently a bit simplistic, it may need to be
    improved to support more configurations and OS.
    """
    globs_to_test = [
        "/dev/tty*FTOA2PV*",
        "/dev/serial/by-id/*EnOcean*",
        "/dev/tty.usbserial-*",
    ]
    found_paths = []
    for current_glob in globs_to_test:
        found_paths.extend(glob.glob(current_glob))

    return found_paths


class EnOceanFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle the enOcean config flows."""

    VERSION = 2
    MINOR_VERSION = 1
    MANUAL_PATH_VALUE = "manual"

    def __init__(self) -> None:
        """Initialize the EnOcean config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle usb discovery."""
        unique_id = usb_unique_id_from_service_info(discovery_info)

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_DEVICE: discovery_info.device}
        )

        discovery_info.device = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )

        self.data[CONF_DEVICE] = discovery_info.device
        self.context["title_placeholders"] = {
            CONF_NAME: human_readable_device_name(
                discovery_info.device,
                discovery_info.serial_number,
                discovery_info.manufacturer,
                discovery_info.description,
                discovery_info.vid,
                discovery_info.pid,
            )
        }
        return await self.async_step_usb_confirm()

    async def async_step_usb_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle USB Discovery confirmation."""
        if user_input is not None:
            return await self.async_step_manual({CONF_DEVICE: self.data[CONF_DEVICE]})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="usb_confirm",
            description_placeholders={
                ATTR_MANUFACTURER: MANUFACTURER,
                CONF_DEVICE: self.data.get(CONF_DEVICE, ""),
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an EnOcean config flow start."""
        return await self.async_step_detect()

    async def async_step_detect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Propose a list of detected dongles."""
        if user_input is not None:
            if user_input[CONF_DEVICE] == self.MANUAL_PATH_VALUE:
                return await self.async_step_manual()
            if await self.validate_enocean_conf(user_input):
                return self.async_create_entry(title="EnOcean", data=user_input)

        devices = await self.hass.async_add_executor_job(_detect_usb_dongle)
        if len(devices) == 0:
            return await self.async_step_manual()
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
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Request manual USB dongle path."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if await self.validate_enocean_conf(user_input):
                return self.async_create_entry(title="EnOcean", data=user_input)

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(MANUAL_SCHEMA, user_input),
            errors=errors,
        )

    async def validate_enocean_conf(self, user_input: Any) -> bool:
        """Return True if the user_input contains a valid dongle path."""
        dongle_path = user_input[CONF_DEVICE]

        try:
            # Starting the gateway will raise an exception if it can't connect
            gateway = Gateway(port=dongle_path)
            await gateway.start()
        except ConnectionError as exception:
            LOGGER.warning("Dongle path %s is invalid: %s", dongle_path, str(exception))
            return False
        finally:
            gateway.stop()

        return True

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: EnOceanConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle an option flow for EnOcean."""

    async def async_step_init(self, user_input: Any | None = None) -> ConfigFlowResult:
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

    async def async_step_add_device(
        self, user_input: Any | None = None
    ) -> ConfigFlowResult:
        """Add an EnOcean device."""
        errors: dict[str, str] = {}
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))

        add_device_schema = None

        default_device_type = ""
        default_device_id = ""
        gateway: Gateway = self.config_entry.runtime_data
        default_sender_id = str(await gateway.base_id)

        device_id: EnOceanDeviceAddress | None = None
        sender_id: EnOceanAddress | None = None

        if user_input is not None:
            # device id must be a valid EnOcean ID and not already configured
            if not EnOceanDeviceAddress.validate_string(
                user_input[CONF_ENOCEAN_DEVICE_ID]
            ):
                errors[CONF_ENOCEAN_DEVICE_ID] = ENOCEAN_ERROR_INVALID_DEVICE_ID

            else:
                device_id = EnOceanDeviceAddress(user_input[CONF_ENOCEAN_DEVICE_ID])

                for dev in devices:
                    if not EnOceanDeviceAddress.validate_string(
                        dev[CONF_ENOCEAN_DEVICE_ID]
                    ):
                        continue
                    if (
                        EnOceanDeviceAddress(dev[CONF_ENOCEAN_DEVICE_ID]).to_number()
                        == device_id.to_number()
                    ):
                        errors[CONF_ENOCEAN_DEVICE_ID] = (
                            ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED
                        )
                        break

            device_type_id = user_input[ENOCEAN_DEVICE_TYPE_ID]

            # sender id must be a valid EnOcean address string
            if user_input[CONF_ENOCEAN_SENDER_ID].strip() == "":
                sender_id = await gateway.base_id
            elif not EnOceanAddress.validate_string(user_input[CONF_ENOCEAN_SENDER_ID]):
                errors[CONF_ENOCEAN_SENDER_ID] = ENOCEAN_ERROR_INVALID_SENDER_ID
            else:
                sender_id = EnOceanAddress(user_input[CONF_ENOCEAN_SENDER_ID])

            # append to the configuration if no errors
            if not errors:
                assert device_id is not None
                assert sender_id is not None
                devices.append(
                    {
                        CONF_ENOCEAN_DEVICE_ID: str(device_id),
                        CONF_ENOCEAN_DEVICE_TYPE_ID: device_type_id,
                        CONF_ENOCEAN_SENDER_ID: str(sender_id),
                    }
                )

                return self.async_create_entry(
                    title="EnOcean device", data={CONF_ENOCEAN_DEVICES: devices}
                )

            default_device_type = device_type_id
            default_device_id = str(device_id) if device_id else ""
            default_sender_id = str(sender_id) if sender_id else ""

        supported_devices = [
            selector.SelectOptionDict(value=dt.id, label=_device_type_label(dt))
            for dt in DEVICE_TYPES.values()
        ]
        supported_devices.sort(key=lambda entry: entry["label"].upper())

        sender_options = [str(s) for s in (await gateway.sender_slots)]

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
                    CONF_ENOCEAN_SENDER_ID,
                    default=default_sender_id,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sender_options,
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
        self, user_input: Any | None = None
    ) -> ConfigFlowResult:
        """Select a configured EnOcean device to edit."""
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))
        device_list = [
            selector.SelectOptionDict(
                value=device[CONF_ENOCEAN_DEVICE_ID],
                label=device[CONF_ENOCEAN_DEVICE_ID],
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
        self, user_input: Any | None = None, device: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit an EnOcean device."""
        errors: dict[str, str] = {}
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))

        device_id = "00:00:00:00"
        device_type_id: str = ""
        sender_id: EnOceanAddress = EnOceanAddress(0)
        sender_id_string: str = ""

        gateway: Gateway = self.config_entry.runtime_data

        if device is not None:  # user_input will be ignored in this case
            device_id = device[CONF_ENOCEAN_DEVICE_ID]
            device_type_id = device[CONF_ENOCEAN_DEVICE_TYPE_ID]
            sender_id_string = device[CONF_ENOCEAN_SENDER_ID]

        elif user_input is not None:
            # device id needs no validation as user cannot change it
            device_id = user_input[CONF_ENOCEAN_DEVICE_ID]

            # sender id must be either empty or a valid EnOcean ID
            sender_id_string = user_input[CONF_ENOCEAN_SENDER_ID].strip()
            if sender_id_string != "":
                if EnOceanAddress.validate_string(sender_id_string):
                    sender_id = EnOceanAddress(sender_id_string)
                else:
                    errors[CONF_ENOCEAN_SENDER_ID] = ENOCEAN_ERROR_INVALID_SENDER_ID

            device_type_id = user_input[ENOCEAN_DEVICE_TYPE_ID]

            if not errors:
                for dev in devices:
                    if dev[CONF_ENOCEAN_DEVICE_ID] == device_id:
                        dev[CONF_ENOCEAN_DEVICE_TYPE_ID] = device_type_id
                        dev[CONF_ENOCEAN_SENDER_ID] = str(sender_id)
                        break

                return self.async_create_entry(
                    title="", data={CONF_ENOCEAN_DEVICES: devices}
                )

        supported_devices = [
            selector.SelectOptionDict(value=dt.id, label=_device_type_label(dt))
            for dt in DEVICE_TYPES.values()
        ]
        supported_devices.sort(key=lambda entry: entry["label"].upper())

        sender_options = [str(s) for s in (await gateway.sender_slots)]

        edit_device_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENOCEAN_DEVICE_ID, default=device_id
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=[device_id])
                ),
                vol.Required(
                    ENOCEAN_DEVICE_TYPE_ID, default=device_type_id
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=supported_devices)
                ),
                vol.Optional(
                    CONF_ENOCEAN_SENDER_ID, default=sender_id_string
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sender_options,
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

    async def async_step_delete_device(
        self, user_input: Any | None = None
    ) -> ConfigFlowResult:
        """Delete an EnOcean device."""
        devices = deepcopy(self.config_entry.options.get(CONF_ENOCEAN_DEVICES, []))
        device_list = [
            selector.SelectOptionDict(
                value=device[CONF_ENOCEAN_DEVICE_ID],
                label=device[CONF_ENOCEAN_DEVICE_ID],
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

    def create_enocean_entry(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the provided configuration."""
        return self.async_create_entry(title=MANUFACTURER, data=user_input)

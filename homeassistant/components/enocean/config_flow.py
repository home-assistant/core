"""Config flows for the EnOcean integration."""

from typing import Any

from enocean_async import Gateway
import voluptuous as vol

from homeassistant.components.usb import (
    USBDevice,
    get_serial_by_id,
    human_readable_device_name,
    scan_serial_ports,
    usb_service_info_from_device,
    usb_unique_id_from_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import ATTR_MANUFACTURER, CONF_DEVICE, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import (
    CONFIG_FLOW_MINOR_VERSION,
    CONFIG_FLOW_VERSION,
    DOMAIN,
    ERROR_INVALID_DONGLE_PATH,
    LOGGER,
    MANUFACTURER,
)

MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): cv.string,
    }
)


def get_human_readable_device_name(
    info: UsbServiceInfo,
) -> str:
    """Return a human readable device name."""
    return human_readable_device_name(
        info.device,
        info.serial_number,
        info.manufacturer,
        info.description,
        info.vid,
        info.pid,
    )


class EnOceanFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle the enOcean config flows."""

    VERSION = CONFIG_FLOW_VERSION
    MINOR_VERSION = CONFIG_FLOW_MINOR_VERSION
    MANUAL_PATH_VALUE = "manual"

    def __init__(self) -> None:
        """Initialize the EnOcean config flow."""
        self.data: dict[str, Any] = {}
        self._ports: list[USBDevice] | None = None

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle usb discovery."""
        await self._async_update_device_and_set_unique_id(discovery_info)

        self.data[CONF_DEVICE] = discovery_info.device
        self.context["title_placeholders"] = {
            CONF_NAME: get_human_readable_device_name(discovery_info)
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

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a yaml configuration."""

        if not await self.validate_enocean_conf(import_data):
            LOGGER.warning(
                "Cannot import yaml configuration: %s is not a valid dongle path",
                import_data[CONF_DEVICE],
            )
            return self.async_abort(reason="invalid_dongle_path")

        return self.create_enocean_entry(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an EnOcean config flow start."""
        if self._ports is None:
            self._ports = []
            self._ports.extend(
                await self.hass.async_add_executor_job(scan_serial_ports)
            )

        if user_input is not None:
            if user_input[CONF_DEVICE] == self.MANUAL_PATH_VALUE:
                return await self.async_step_manual()

            selected_device = next(
                (
                    port
                    for port in self._ports
                    if port.device == user_input[CONF_DEVICE]
                ),
                None,
            )
            if selected_device is None:
                return self.async_abort(reason="unknown_device")
            selected_service = usb_service_info_from_device(selected_device)

            await self._async_update_device_and_set_unique_id(selected_service)
            user_input[CONF_DEVICE] = selected_service.device

            return await self.async_step_manual(user_input)

        if len(self._ports) == 0:
            # Move on to manual step if no ports are found
            return await self.async_step_manual()

        devices = [
            SelectOptionDict(
                value=port.device,
                label=get_human_readable_device_name(
                    usb_service_info_from_device(port)
                ),
            )
            for port in self._ports
        ]
        devices.append(
            SelectOptionDict(value=self.MANUAL_PATH_VALUE, label=self.MANUAL_PATH_VALUE)
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): SelectSelector(
                        SelectSelectorConfig(
                            options=devices,
                            translation_key="devices",
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Request manual USB dongle path."""
        errors = {}
        if user_input is not None:
            if await self.validate_enocean_conf(user_input):
                return self.create_enocean_entry(user_input)
            errors = {CONF_DEVICE: ERROR_INVALID_DONGLE_PATH}

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(MANUAL_SCHEMA, user_input),
            errors=errors,
        )

    async def validate_enocean_conf(self, user_input) -> bool:
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

    def create_enocean_entry(self, user_input):
        """Create an entry for the provided configuration."""
        return self.async_create_entry(title=MANUFACTURER, data=user_input)

    async def _async_update_device_and_set_unique_id(
        self, usb_service_info: UsbServiceInfo
    ) -> None:
        """Normalize the USB device serial and set unique ID depending on it."""
        # normalize device path
        usb_service_info.device = await self.hass.async_add_executor_job(
            get_serial_by_id, usb_service_info.device
        )
        # set unique id
        unique_id = usb_unique_id_from_service_info(usb_service_info)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_DEVICE: usb_service_info.device}
        )

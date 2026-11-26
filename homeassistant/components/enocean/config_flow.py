"""Config flows for the EnOcean integration."""

import glob
from typing import Any, override

from enocean_async import Gateway
from enocean_async.address import Address
import probatio

from homeassistant.components import usb
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.usb import (
    human_readable_device_name,
    usb_unique_id_from_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_DEVICE_CLASS, CONF_ID
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import (
    CONF_DEVICE_TYPE_ID,
    DEVICE_TYPE_ROCKER_SWITCH,
    DOMAIN,
    ERROR_INVALID_DEVICE_ID,
    ERROR_INVALID_DONGLE_PATH,
    LOGGER,
    MANUFACTURER,
    SUBENTRY_TYPE_DEVICE,
)

MANUAL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): cv.string,
    }
)

DEVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ID): cv.string,
        probatio.Optional(CONF_DEVICE_CLASS): SelectSelector(
            SelectSelectorConfig(
                options=[cls.value for cls in BinarySensorDeviceClass],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="binary_sensor_device_class",
                sort=True,
            )
        ),
    }
)


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

    VERSION = 1
    MANUAL_PATH_VALUE = "manual"

    def __init__(self) -> None:
        """Initialize the EnOcean config flow."""
        self.data: dict[str, Any] = {}

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentries a gateway can have."""
        return {SUBENTRY_TYPE_DEVICE: EnOceanDeviceSubentryFlowHandler}

    @override
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
            "name": human_readable_device_name(
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
        return self.async_show_form(
            step_id="usb_confirm",
            description_placeholders={
                "manufacturer": MANUFACTURER,
                "device": self.data.get(CONF_DEVICE, ""),
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

    @override
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
            return await self.async_step_manual(user_input)

        devices = await self.hass.async_add_executor_job(_detect_usb_dongle)
        if len(devices) == 0:
            return await self.async_step_manual()
        devices.append(self.MANUAL_PATH_VALUE)

        return self.async_show_form(
            step_id="detect",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE): SelectSelector(
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
            await gateway.stop()

        return True

    def create_enocean_entry(self, user_input):
        """Create an entry for the provided configuration."""
        return self.async_create_entry(title=MANUFACTURER, data=user_input)


class EnOceanDeviceSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding an EnOcean device to a gateway."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a rocker switch."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                address = str(Address(user_input[CONF_ID]))
            except ValueError:
                errors[CONF_ID] = ERROR_INVALID_DEVICE_ID
            else:
                if any(
                    subentry.unique_id == address
                    for subentry in self._get_entry().subentries.values()
                ):
                    errors[CONF_ID] = "already_configured_device"
                else:
                    data = {
                        CONF_ID: address,
                        CONF_DEVICE_TYPE_ID: DEVICE_TYPE_ROCKER_SWITCH,
                    }
                    if CONF_DEVICE_CLASS in user_input:
                        data[CONF_DEVICE_CLASS] = user_input[CONF_DEVICE_CLASS]
                    return self.async_create_entry(
                        title=f"Rocker switch {address}", data=data, unique_id=address
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DEVICE_SCHEMA, user_input),
            errors=errors,
        )

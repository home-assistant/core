"""Config flows for the EnOcean integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import usb
from homeassistant.components.usb import (
    human_readable_device_name,
    usb_unique_id_from_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import ATTR_MANUFACTURER, CONF_DEVICE, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from . import dongle
from .const import DOMAIN, ERROR_INVALID_DONGLE_PATH, LOGGER, MANUFACTURER

MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): cv.string,
    }
)


class EnOceanFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle the enOcean config flows."""

    VERSION = 1
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
        return await self.async_step_detect()

    async def async_step_detect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Propose a list of detected dongles."""
        if user_input is not None:
            if user_input[CONF_DEVICE] == self.MANUAL_PATH_VALUE:
                return await self.async_step_manual()
            return await self.async_step_manual(user_input)

        devices = await self.hass.async_add_executor_job(dongle.detect)
        if len(devices) == 0:
            return await self.async_step_manual()
        devices.append(self.MANUAL_PATH_VALUE)

        return self.async_show_form(
            step_id="detect",
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
        return await self.hass.async_add_executor_job(dongle.validate_path, dongle_path)

    def create_enocean_entry(self, user_input):
        """Create an entry for the provided configuration."""
        return self.async_create_entry(title=MANUFACTURER, data=user_input)

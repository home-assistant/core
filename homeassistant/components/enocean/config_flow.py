"""Config flows for the EnOcean integration."""

import asyncio
import glob
from typing import Any, override

from enocean_async import SerialProtocol, detect_serial_protocol
import probatio

from homeassistant.components import usb
from homeassistant.components.usb import (
    human_readable_device_name,
    usb_unique_id_from_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import (
    CONF_PROTOCOL,
    DOMAIN,
    ERROR_INVALID_DONGLE_PATH,
    LOGGER,
    MANUFACTURER,
)

MANUAL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): cv.string,
    }
)


ENOCEAN_DONGLE_GLOBS = ["/dev/tty*FTOA2PV*", "/dev/serial/by-id/*EnOcean*"]
# Matches any USB serial adapter, so these ports are listed without probing them
GENERIC_SERIAL_GLOBS = ["/dev/tty.usbserial-*"]


def _detect_usb_dongle(globs_to_test: list[str]) -> list[str]:
    """Return a list of candidate paths for USB EnOcean dongles.

    This method is currently a bit simplistic, it may need to be
    improved to support more configurations and OS.
    """
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

        protocol = await detect_serial_protocol(import_data[CONF_DEVICE])
        if protocol is None:
            LOGGER.warning(
                "Cannot import yaml configuration: %s is not a valid dongle path",
                import_data[CONF_DEVICE],
            )
            return self.async_abort(reason="invalid_dongle_path")

        return self.create_enocean_entry(import_data, protocol)

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

        candidates = await self.hass.async_add_executor_job(
            _detect_usb_dongle, ENOCEAN_DONGLE_GLOBS
        )
        # Only a port with a dongle is listed: a FAM-USB, for example, shows up as
        # two serial ports, of which one is connected to the radio module.
        protocols = await asyncio.gather(
            *(detect_serial_protocol(path) for path in candidates)
        )
        devices = [
            path
            for path, protocol in zip(candidates, protocols, strict=True)
            if protocol is not None
        ]
        devices.extend(
            await self.hass.async_add_executor_job(
                _detect_usb_dongle, GENERIC_SERIAL_GLOBS
            )
        )
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
            protocol = await detect_serial_protocol(user_input[CONF_DEVICE])
            if protocol is not None:
                return self.create_enocean_entry(user_input, protocol)
            errors = {CONF_DEVICE: ERROR_INVALID_DONGLE_PATH}

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(MANUAL_SCHEMA, user_input),
            errors=errors,
        )

    def create_enocean_entry(
        self, user_input: dict[str, Any], protocol: SerialProtocol
    ) -> ConfigFlowResult:
        """Create an entry for the provided configuration."""
        return self.async_create_entry(
            title=MANUFACTURER, data={**user_input, CONF_PROTOCOL: protocol.value}
        )

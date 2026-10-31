"""Config flow for the Tridonic DALI integration."""

from typing import Any, override

from dali.driver.serial import DriverLubaRs232
import probatio

from homeassistant.components import usb
from homeassistant.components.usb import (
    SerialDevice,
    USBDevice,
    async_scan_serial_ports,
    human_readable_device_name,
    usb_service_info_from_device,
    usb_unique_id_from_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.helpers.selector import SerialPortSelector
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import CONF_BUS_POWER, DOMAIN


def _serial_port_label(port: SerialDevice) -> str:
    """Return a human readable label for a scanned serial port."""
    if isinstance(port, USBDevice):
        return human_readable_device_name(
            port.device,
            port.serial_number,
            port.manufacturer,
            port.description,
            port.vid,
            port.pid,
        )
    return port.device


class DaliConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tridonic DALI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._device: str | None = None
        self._title: str | None = None
        self._offer_bus_power = False
        self._ports: dict[str, SerialDevice] = {}

    async def _async_probe(self, device: str) -> bool:
        """Connect to the interface and report whether it can power the bus.

        Returns True when the interface has a switchable bus power supply, so
        the user can be asked whether to enable it. Raises OSError or
        TimeoutError when the interface cannot be reached.
        """
        driver = DriverLubaRs232(uri=f"luba232:{device}")
        try:
            # Probe read-only: do not write the interface's settings, so a bus
            # already powered by the integrated supply is not depowered.
            await driver.connect(apply_settings=False)
            descriptor = await driver.query_device_descriptor()
        finally:
            if transport := getattr(driver, "_transport", None):
                transport.close()
        if descriptor is None:
            raise OSError("Unable to read the DALI interface descriptor")
        return bool(descriptor.has_bus_power_supply)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manually initiated flow by selecting a serial port."""
        self._ports = {
            port.device: port for port in await async_scan_serial_ports(self.hass)
        }
        if not self._ports:
            return self.async_abort(reason="no_serial_ports")

        errors: dict[str, str] = {}
        # The form was rendered from an earlier scan, so the chosen port may have
        # been unplugged before submission; fall back to the refreshed list.
        if user_input is not None and (
            port := self._ports.get(user_input[CONF_DEVICE])
        ):
            if isinstance(port, USBDevice):
                await self.async_set_unique_id(
                    usb_unique_id_from_service_info(usb_service_info_from_device(port))
                )
                self._abort_if_unique_id_configured()
            else:
                await self.async_set_unique_id(None)
            device = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, port.device
            )
            self._async_abort_entries_match({CONF_DEVICE: device})
            try:
                self._offer_bus_power = await self._async_probe(device)
            except OSError, TimeoutError:
                errors["base"] = "cannot_connect"
            else:
                self._device = device
                self._title = _serial_port_label(port)
                return await self.async_step_bus_power()
        elif user_input is not None:
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_DEVICE): SerialPortSelector()}
            ),
            errors=errors,
        )

    @override
    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle discovery of a Lunatone USB-DALI2 interface."""
        await self.async_set_unique_id(usb_unique_id_from_service_info(discovery_info))
        self._device = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )
        self._abort_if_unique_id_configured(updates={CONF_DEVICE: self._device})
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
        try:
            self._offer_bus_power = await self._async_probe(self._device)
        except OSError, TimeoutError:
            return self.async_abort(reason="cannot_connect")
        return await self.async_step_usb_confirm()

    async def async_step_usb_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered USB-DALI2 interface."""
        if user_input is not None:
            self._title = self.context["title_placeholders"][CONF_NAME]
            return await self.async_step_bus_power()
        self._set_confirm_only()
        return self.async_show_form(step_id="usb_confirm")

    async def async_step_bus_power(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optionally switch on the interface's integrated bus power supply."""
        if not self._offer_bus_power:
            return self._create_entry(bus_power=False)
        if user_input is not None:
            return self._create_entry(bus_power=user_input[CONF_BUS_POWER])
        return self.async_show_form(
            step_id="bus_power",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_BUS_POWER, default=False): bool}
            ),
        )

    def _create_entry(self, *, bus_power: bool) -> ConfigFlowResult:
        """Create the config entry for the selected interface."""
        assert self._device is not None
        assert self._title is not None
        # Another manual flow may have configured the same port while this one
        # waited at the bus-power step; manual ports have no unique ID for the
        # flow manager to deduplicate, so re-check before creating the entry.
        self._async_abort_entries_match({CONF_DEVICE: self._device})
        return self.async_create_entry(
            title=self._title,
            data={CONF_DEVICE: self._device, CONF_BUS_POWER: bus_power},
        )

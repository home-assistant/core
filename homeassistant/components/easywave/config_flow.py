"""Config flow for the Easywave gateway."""

import logging
from typing import Any, override

import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .config_flow_subentry import EasywaveDeviceSubentryFlowHandler
from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
    SUBENTRY_DEVICE,
    SUPPORTED_USB_IDS,
    USB_DEVICE_NAMES,
    get_frequency_for_pid,
    is_country_allowed_for_frequency,
)
from .transceiver import RX11Transceiver

_LOGGER = logging.getLogger(__name__)


class EasywaveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Easywave gateway setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._device: dict[str, Any] = {}

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_DEVICE: EasywaveDeviceSubentryFlowHandler}

    def _abort_if_frequency_not_permitted(
        self, pid: int | None
    ) -> ConfigFlowResult | None:
        """Abort when the transceiver frequency is not allowed in the user's country."""
        frequency = get_frequency_for_pid(pid)
        country = self.hass.config.country
        if frequency and not is_country_allowed_for_frequency(frequency, country):
            return self.async_abort(
                reason="frequency_not_permitted",
                description_placeholders={
                    "frequency": frequency,
                    "country": country or "unknown",
                },
            )
        return None

    async def _async_validate_device_connection(self, device_path: str) -> bool:
        """Verify that an RX11 transceiver is reachable on the given port."""
        transceiver = RX11Transceiver(self.hass, device_path)
        try:
            return await transceiver.connect()
        finally:
            await transceiver.dispose()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Entry point for adding the RX11 gateway."""
        return await self.async_step_ports()

    async def async_step_ports(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show available RX11 serial ports and let the user pick one."""
        errors: dict[str, str] = {}
        try:
            ports = [
                port
                for port in await self.hass.async_add_executor_job(
                    serial.tools.list_ports.comports
                )
                if port.vid is not None
                and port.pid is not None
                and (port.vid, port.pid) in SUPPORTED_USB_IDS
            ]
        except OSError:
            return self.async_abort(reason="no_devices_found")

        port_list = {
            p.device: (
                f"{p.device}"
                f"{f', s/n: {p.serial_number}' if p.serial_number else ''}"
                f"{f' - {p.manufacturer}' if p.manufacturer else ''}"
            )
            for p in ports
        }

        if not port_list:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            selected_path = user_input[CONF_DEVICE_PATH]
            port = next((p for p in ports if p.device == selected_path), None)
            if port is None:
                errors["base"] = "device_no_longer_available"
            else:
                self._device = {
                    "device": port.device,
                    "vid": port.vid,
                    "pid": port.pid,
                    "serial_number": port.serial_number or "unknown",
                    "manufacturer": port.manufacturer or "unknown",
                    "product": (
                        USB_DEVICE_NAMES[(port.vid, port.pid)]["product"]
                        if (port.vid, port.pid) in USB_DEVICE_NAMES
                        else port.product or "Easywave Device"
                    ),
                }
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="ports",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_PATH): vol.In(port_list)}),
            errors=errors,
        )

    @override
    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle USB discovery."""
        vid = int(discovery_info.vid, 16)
        pid = int(discovery_info.pid, 16)
        if (vid, pid) not in SUPPORTED_USB_IDS:
            return self.async_abort(reason="no_devices_found")

        serial_number = discovery_info.serial_number or "unknown"

        unique_id = (
            f"easywave_{serial_number}"
            if serial_number != "unknown"
            else f"easywave_{vid:04X}_{pid:04X}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        device_entry = USB_DEVICE_NAMES.get((vid, pid))
        mfr = device_entry["manufacturer"] if device_entry else "ELDAT EaS GmbH"
        prod = device_entry["product"] if device_entry else "Unknown Easywave Device"

        self._device = {
            "device": discovery_info.device,
            "vid": vid,
            "pid": pid,
            "serial_number": serial_number,
            "manufacturer": discovery_info.manufacturer or mfr,
            "product": prod,
        }
        self.context["title_placeholders"] = {"name": prod}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show confirmation dialog and create the gateway entry on submit."""
        serial_number = self._device["serial_number"]
        vid = self._device.get("vid")
        pid = self._device.get("pid")

        if serial_number != "unknown":
            unique_id = f"easywave_{serial_number}"
        elif vid is not None and pid is not None:
            unique_id = f"easywave_{vid:04X}_{pid:04X}"
        else:
            unique_id = f"easywave_{self._device['device'].replace('/', '_')}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        if abort := self._abort_if_frequency_not_permitted(pid):
            return abort

        if user_input is not None:
            d = self._device
            if not await self._async_validate_device_connection(d["device"]):
                return self.async_show_form(
                    step_id="confirm",
                    data_schema=vol.Schema({}),
                    errors={"base": "cannot_connect"},
                    description_placeholders={
                        "name": self._device["product"],
                        "serial_number": serial_number,
                        "device": self._device["device"],
                    },
                )
            return self.async_create_entry(
                title=d["product"],
                data={
                    CONF_DEVICE_PATH: d["device"],
                    CONF_USB_VID: d["vid"],
                    CONF_USB_PID: d["pid"],
                    CONF_USB_SERIAL_NUMBER: d["serial_number"],
                    CONF_USB_MANUFACTURER: d["manufacturer"],
                    CONF_USB_PRODUCT: d["product"],
                },
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._device["product"],
                "serial_number": serial_number,
                "device": self._device["device"],
            },
        )

"""Config flow for the Easywave integration."""

from __future__ import annotations

import logging
from typing import Any

import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
    SUPPORTED_USB_IDS,
    USB_DEVICE_NAMES,
)

_LOGGER = logging.getLogger(__name__)


def _find_easywave_devices() -> list[dict[str, Any]]:
    """Scan serial ports and return info dicts for all supported Easywave sticks.

    Runs in an executor (blocking I/O).
    """
    devices: list[dict[str, Any]] = []
    try:
        for port in serial.tools.list_ports.comports():
            if (port.vid, port.pid) in SUPPORTED_USB_IDS:
                device_entry = USB_DEVICE_NAMES.get((port.vid, port.pid))
                mfr = device_entry["manufacturer"] if device_entry else "ELDAT EaS GmbH"
                prod = (
                    device_entry["product"]
                    if device_entry
                    else "Unknown Easywave Device"
                )
                devices.append(
                    {
                        "device": port.device,
                        "vid": port.vid,
                        "pid": port.pid,
                        "serial_number": port.serial_number or "unknown",
                        "manufacturer": port.manufacturer or mfr,
                        "product": prod,
                    }
                )
    except Exception:
        _LOGGER.exception("Error scanning for Easywave USB devices")
    return devices


class EasywaveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Easywave."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._device: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Entry point: start auto-detection immediately
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort if already configured, otherwise start auto-detection."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        return await self.async_step_detect()

    # ------------------------------------------------------------------
    # Auto-detection step
    # ------------------------------------------------------------------

    async def async_step_detect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Scan for connected Easywave sticks and proceed to confirmation."""
        devices = await self.hass.async_add_executor_job(_find_easywave_devices)

        if not devices:
            return self.async_abort(reason="no_devices_found")

        # Auto-select when exactly one device is present.
        if len(devices) == 1:
            self._device = devices[0]
            return await self.async_step_confirm()

        # Multiple devices: let the user pick one.
        if user_input is not None:
            selected_path = user_input[CONF_DEVICE_PATH]
            self._device = next(d for d in devices if d["device"] == selected_path)
            return await self.async_step_confirm()

        options = [
            SelectOptionDict(
                value=d["device"],
                label=f"{d['product']} — {d['device']} ({d['serial_number']})",
            )
            for d in devices
        ]
        return self.async_show_form(
            step_id="detect",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_PATH): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(devices))},
        )

    # ------------------------------------------------------------------
    # USB auto-discovery (triggered by manifest `usb` matcher)
    # ------------------------------------------------------------------

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle USB discovery."""
        vid = int(discovery_info.vid, 16)
        pid = int(discovery_info.pid, 16)
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

    # ------------------------------------------------------------------
    # Confirmation step
    # ------------------------------------------------------------------

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show confirmation dialog and create the entry on submit."""
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

        if user_input is not None:
            return self._create_entry()

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._device["product"],
                "serial_number": serial_number,
                "device": self._device["device"],
            },
        )

    # ------------------------------------------------------------------

    def _create_entry(self) -> ConfigFlowResult:
        """Create the config entry."""
        d = self._device
        return self.async_create_entry(
            title="Easywave Gateway",
            data={
                CONF_DEVICE_PATH: d["device"],
                CONF_USB_VID: d["vid"],
                CONF_USB_PID: d["pid"],
                CONF_USB_SERIAL_NUMBER: d["serial_number"],
                CONF_USB_MANUFACTURER: d["manufacturer"],
                CONF_USB_PRODUCT: d["product"],
            },
        )

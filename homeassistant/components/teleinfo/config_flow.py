"""Config flow for the Teleinfo integration."""

import logging
from typing import TYPE_CHECKING, Any

import serial
from teleinfo import decode, read_frame
import voluptuous as vol

from homeassistant.components import usb
from homeassistant.components.usb import human_readable_device_name
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import CONF_SERIAL_PORT, CONF_USB_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): str,
    }
)


class TeleinfoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Teleinfo."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the Teleinfo config flow."""
        self._discovered_device: str | None = None
        self._discovered_usb_serial_number: str | None = None

    async def _validate_serial_port(
        self, serial_port: str
    ) -> tuple[dict[str, str], dict[str, str] | None]:
        """Validate the serial port by reading and decoding a Teleinfo frame.

        Returns a tuple of (errors, decoded_data). On success errors is empty and
        decoded_data contains the label/value pairs. On failure decoded_data is None.
        """
        errors: dict[str, str] = {}
        try:
            frame = await self.hass.async_add_executor_job(read_frame, serial_port)
            decoded_data: dict[str, str] = decode(frame)
        except serial.SerialException:
            errors["base"] = "cannot_connect"
            return errors, None
        except TimeoutError:
            errors["base"] = "timeout_connect"
            return errors, None
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return errors, None
        return errors, decoded_data

    async def _resolve_usb_serial_number(self, serial_port: str) -> str | None:
        """Return the USB serial number for a serial port, if it is a USB device.

        This only reads USB descriptors (no serial port is opened), so it is safe
        to call without disturbing the device or other integrations.
        """
        device = await self.hass.async_add_executor_job(
            usb.usb_device_from_path, serial_port
        )
        return device.serial_number if device is not None else None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            serial_port = user_input[CONF_SERIAL_PORT]
            errors, decoded_data = await self._validate_serial_port(serial_port)
            if not errors:
                assert decoded_data is not None
                adco = decoded_data["ADCO"]
                await self.async_set_unique_id(adco)
                self._abort_if_unique_id_configured()
                data: dict[str, str] = {CONF_SERIAL_PORT: serial_port}
                usb_serial_number = await self._resolve_usb_serial_number(serial_port)
                if usb_serial_number is not None:
                    data[CONF_USB_SERIAL_NUMBER] = usb_serial_number
                return self.async_create_entry(
                    title=f"Teleinfo ({serial_port})",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle USB discovery.

        No serial port is opened here: the device is only opened once the user
        explicitly confirms the discovery, so a discovered dongle that actually
        belongs to another integration is never disturbed.
        """
        # Resolve stable /dev/serial/by-id/ path
        dev_path = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )
        usb_serial_number = discovery_info.serial_number
        # The USB matcher in manifest.json requires a `tinfo-*` serial number,
        # so discovery is only ever invoked for devices that expose one.
        assert usb_serial_number is not None

        # If a config entry already exists for this dongle, update its serial
        # port path (the dongle may have been re-plugged) and abort. The entry
        # is keyed by the meter ADCO, which we cannot read without opening the
        # port, so the dongle USB serial stored in the entry is used to match.
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data.get(CONF_USB_SERIAL_NUMBER) != usb_serial_number:
                continue
            if entry.data.get(CONF_SERIAL_PORT) != dev_path:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_SERIAL_PORT: dev_path},
                    title=f"Teleinfo ({dev_path})",
                )
            return self.async_abort(reason="already_configured")

        # Dedupe concurrent discovery flows for the same dongle. The entry's
        # unique_id becomes the meter ADCO once the user confirms.
        await self.async_set_unique_id(usb_serial_number)

        self._discovered_device = dev_path
        self._discovered_usb_serial_number = usb_serial_number
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
        """Handle USB discovery confirmation."""
        if TYPE_CHECKING:
            assert self._discovered_device is not None
        if user_input is not None:
            # The user confirmed: now it is safe to open the port and validate
            # that this really is a Teleinfo meter.
            errors, decoded_data = await self._validate_serial_port(
                self._discovered_device
            )
            if errors or decoded_data is None:
                return self.async_abort(reason="not_teleinfo_device")

            adco = decoded_data["ADCO"]
            await self.async_set_unique_id(adco)
            data: dict[str, str] = {CONF_SERIAL_PORT: self._discovered_device}
            if self._discovered_usb_serial_number is not None:
                data[CONF_USB_SERIAL_NUMBER] = self._discovered_usb_serial_number
            # If an entry already exists for this meter (e.g. added manually,
            # or the dongle was replaced), refresh its serial port path and
            # backfill the USB serial number so future rediscovery can match
            # it without opening the port.
            self._abort_if_unique_id_configured(updates=data)

            return self.async_create_entry(
                title=f"Teleinfo ({self._discovered_device})",
                data=data,
            )
        self._set_confirm_only()
        return self.async_show_form(step_id="usb_confirm")

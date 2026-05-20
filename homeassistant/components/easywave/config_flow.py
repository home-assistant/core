"""Config flow for the Easywave integration."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any
import uuid

import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import (
    CONF_BUTTON_COUNT,
    CONF_DEVICE_PATH,
    CONF_ENTRY_TYPE,
    CONF_GATEWAY_INDEX,
    CONF_GATEWAY_SERIAL,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_RECEIVER_KIND,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
    ENTRY_TYPE_RECEIVER,
    ENTRY_TYPE_TRANSMITTER,
    LEARNING_TIMEOUT,
    RECEIVER_KIND_UNIVERSAL,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
    USB_DEVICE_NAMES,
)

_LOGGER = logging.getLogger(__name__)

_BUTTON_COUNT_MAP: dict[str, int] = {
    "buttons_1": 1,
    "buttons_2": 2,
    "buttons_3": 3,
    "buttons_4": 4,
}


if TYPE_CHECKING:
    _MixinBase = ConfigFlow
else:
    _MixinBase = object


class _EasywaveDeviceMixin(_MixinBase):
    """Shared device-learning flow steps.

    Used by EasywaveConfigFlow to add devices to an existing gateway
    via the '+' (Add entry) button.

    Subclasses must implement:
    - _get_coordinator() -> coordinator or None
    - _get_devices() -> list[dict]
    - _update_devices(devices) -> ConfigFlowResult
    """

    def _init_device_mixin(self) -> None:
        """Initialize shared device-learning state fields."""
        self._receiver_kind: str | None = None
        self._receiver_gateway_index: int | None = None
        self._receiver_gateway_serial: str | None = None
        self._grouping_mode: str = TRANSMITTER_GROUPING_GROUP
        self._switch_mode: str = TRANSMITTER_SWITCH_IMPULSE
        self._button_count: int = 4
        self._learn_task: asyncio.Task[dict[str, Any] | None] | None = None
        self._learned_device: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Abstract interface (implemented by each concrete flow)
    # ------------------------------------------------------------------

    def _get_coordinator(self) -> Any | None:
        """Return the gateway coordinator or None."""
        raise NotImplementedError

    def _get_devices(self) -> list[dict[str, Any]]:
        """Return the current list of configured devices."""
        raise NotImplementedError

    def _update_devices(self, devices: list[dict[str, Any]]) -> ConfigFlowResult:
        """Persist the updated device list and finish the flow."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def _is_duplicate(self, unique_id: str) -> bool:
        """Return True if a device with this unique_id is already configured."""
        return any(d.get("unique_id") == unique_id for d in self._get_devices())

    def _used_gateway_indices(self) -> set[int]:
        """Return gateway indices already in use by receiver devices."""
        return {
            d["data"][CONF_GATEWAY_INDEX]
            for d in self._get_devices()
            if d["data"].get(CONF_ENTRY_TYPE) == ENTRY_TYPE_RECEIVER
        }

    def _save_device(
        self, title: str, unique_id: str, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Append a new device and persist via _update_devices."""
        devices = self._get_devices()
        devices.append(
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "unique_id": unique_id,
                "data": data,
            }
        )
        return self._update_devices(devices)

    def _next_default_name(self, entry_type: str) -> str:
        """Return a suggested device name based on the existing device count.

        Receivers use the gateway index (1..128) so the name stays stable per
        slot; transmitters use the count of existing devices
        of the same kind +1, since they have no fixed slot.
        """
        if entry_type == ENTRY_TYPE_RECEIVER:
            if self._receiver_gateway_index is None:
                return "EW Receiver"
            return f"EW Receiver {self._receiver_gateway_index + 1}"
        if entry_type == ENTRY_TYPE_TRANSMITTER:
            count = sum(
                1
                for d in self._get_devices()
                if d["data"].get(CONF_ENTRY_TYPE) == ENTRY_TYPE_TRANSMITTER
            )
            return f"EW Transmitter {count + 1}"
        return ""

    # ------------------------------------------------------------------
    # Device menu
    # ------------------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show device management menu."""
        coordinator = self._get_coordinator()
        if coordinator is None:
            return self.async_abort(reason="device_not_connected")
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_receiver",
                "add_transmitter",
            ],
        )

    # ------------------------------------------------------------------
    # Receiver path
    # ------------------------------------------------------------------

    async def async_step_add_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select operating mode for the new receiver."""
        coordinator = self._get_coordinator()
        if coordinator is None or not coordinator.transceiver.is_connected:
            return self.async_abort(reason="device_not_connected")
        return self.async_show_menu(
            step_id="add_receiver",
            menu_options=["mode_universal"],
        )

    async def async_step_mode_universal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle universal mode selection."""
        self._receiver_kind = RECEIVER_KIND_UNIVERSAL
        return await self.async_step_receiver_prepare()

    async def async_step_receiver_prepare(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Instruct the user to put the receiver into its learning mode.

        We allocate the next free gateway index here so the user can verify
        connectivity before any telegram is sent.  When the user confirms,
        :meth:`async_step_receiver_learn_start` emits the actual learning
        command.
        """
        coordinator = self._get_coordinator()
        if coordinator is None or not coordinator.transceiver.is_connected:
            return self.async_abort(reason="device_not_connected")

        if self._receiver_gateway_index is None:
            used_indices = self._used_gateway_indices()
            try:
                gateway_index = next(i for i in range(99) if i not in used_indices)
            except StopIteration:
                return self.async_abort(reason="no_available_receivers")

            gateway_serial = await coordinator.transceiver.get_gateway_serial(
                gateway_index
            )
            if gateway_serial is None:
                return self.async_abort(reason="cannot_get_gateway_serial")

            self._receiver_gateway_index = gateway_index
            self._receiver_gateway_serial = gateway_serial.hex()

        if user_input is not None:
            return await self.async_step_receiver_learn_start()

        return self.async_show_form(
            step_id="receiver_prepare",
            data_schema=vol.Schema({}),
        )

    async def async_step_receiver_learn_start(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Send a learning command to the pre-allocated receiver slot.

        The receiver enters its learning mode the first time it receives any
        valid Easywave command from a not-yet-paired gateway.  We emit a
        single button-A press so the user can confirm via the device's LED
        that the pairing was accepted.
        """
        coordinator = self._get_coordinator()
        if coordinator is None or not coordinator.transceiver.is_connected:
            return self.async_abort(reason="device_not_connected")

        if self._receiver_gateway_serial is None:
            # Should not happen: prepare step allocates the slot.
            return await self.async_step_receiver_prepare()

        gateway_serial = bytes.fromhex(self._receiver_gateway_serial)

        # Send a "button A" press so the receiver's LED acknowledges learning.
        if not await coordinator.transceiver.send_command(gateway_serial, 0):
            return self.async_abort(reason="code_send_failed")

        return await self.async_step_receiver_confirm_learning()

    async def async_step_receiver_confirm_learning(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for user confirmation that the receiver acknowledged learning."""
        return self.async_show_menu(
            step_id="receiver_confirm_learning",
            menu_options=["receiver_name", "receiver_learn_start"],
        )

    async def async_step_receiver_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the receiver name and save the pre-allocated device."""
        if (
            self._receiver_gateway_index is None
            or self._receiver_gateway_serial is None
            or self._receiver_kind is None
        ):
            return self.async_abort(reason="device_not_connected")

        if user_input is not None:
            gateway_index = self._receiver_gateway_index
            serial_hex = self._receiver_gateway_serial
            unique_id = f"receiver_{serial_hex}_{gateway_index}"
            return self._save_device(
                title=user_input["name"],
                unique_id=unique_id,
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
                    CONF_GATEWAY_INDEX: gateway_index,
                    CONF_GATEWAY_SERIAL: serial_hex,
                    CONF_RECEIVER_KIND: self._receiver_kind,
                },
            )

        return self.async_show_form(
            step_id="receiver_name",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "name",
                        default=self._next_default_name(ENTRY_TYPE_RECEIVER),
                    ): str,
                }
            ),
        )

    # ------------------------------------------------------------------
    # Transmitter path
    # ------------------------------------------------------------------

    async def async_step_add_transmitter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a type-1 group-impulse transmitter (the only supported type)."""
        coordinator = self._get_coordinator()
        if coordinator is None or not coordinator.transceiver.is_connected:
            return self.async_abort(reason="device_not_connected")
        return await self.async_step_button_count_select()

    async def async_step_button_count_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select number of transmitter buttons."""
        return self.async_show_menu(
            step_id="button_count_select",
            menu_options=list(_BUTTON_COUNT_MAP),
        )

    async def _async_set_button_count(self, count_key: str) -> ConfigFlowResult:
        self._button_count = _BUTTON_COUNT_MAP[count_key]
        return await self.async_step_learn()

    async def async_step_buttons_1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """1 button."""
        return await self._async_set_button_count("buttons_1")

    async def async_step_buttons_2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """2 buttons."""
        return await self._async_set_button_count("buttons_2")

    async def async_step_buttons_3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """3 buttons."""
        return await self._async_set_button_count("buttons_3")

    async def async_step_buttons_4(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """4 buttons."""
        return await self._async_set_button_count("buttons_4")

    async def async_step_learn(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show progress while waiting for a transmitter telegram."""
        coordinator = self._get_coordinator()
        if coordinator is None or not coordinator.transceiver.is_connected:
            return self.async_abort(reason="device_not_connected")

        if self._learn_task is None:
            self._learn_task = self.hass.async_create_task(
                self._do_transmitter_learning(coordinator),
                "easywave_transmitter_learning",
            )

        if not self._learn_task.done():
            return self.async_show_progress(
                step_id="learn",
                progress_action="waiting_for_transmitter",
                progress_task=self._learn_task,
            )

        try:
            result = self._learn_task.result()
        except OSError, TimeoutError, asyncio.CancelledError:
            result = None
        finally:
            self._learn_task = None

        if result is None:
            return self.async_show_progress_done(next_step_id="learn_timeout")

        self._learned_device = result
        return self.async_show_progress_done(next_step_id="transmitter_confirm")

    async def _do_transmitter_learning(self, coordinator: Any) -> dict[str, Any] | None:
        """Wait for an EW transmitter button press (background task).

        The coordinator's telegram listener is paused for the duration so the
        learning task has exclusive access to the hardware's EWB_RCV channel.
        Sensor telegrams that arrive while waiting are silently
        skipped.
        """
        await coordinator.suspend_telegram_listener()
        try:
            deadline = time.monotonic() + LEARNING_TIMEOUT
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                telegram = await coordinator.transceiver.receive_telegram(
                    timeout=min(remaining, 10.0)
                )
                if telegram is None:
                    continue

                # Only react to button-press telegrams (info_type 0x01).
                # Release (0x00) and sensor data (0x02) are ignored.
                if telegram.get("info_type") != 0x01:
                    continue

                return telegram
        finally:
            coordinator.resume_telegram_listener()

        return None

    async def async_step_learn_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle learning timeout - offer retry or abort."""
        return self.async_show_menu(
            step_id="learn_timeout",
            menu_options=["learn", "abort_learn"],
        )

    async def async_step_abort_learn(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort the transmitter learning flow."""
        return self.async_abort(reason="learning_cancelled")

    async def async_step_transmitter_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the learned transmitter and save."""
        if self._learned_device is None:
            return self.async_abort(reason="no_device_learned")

        serial_hex = self._learned_device["serial"].hex()
        unique_id = f"transmitter_{serial_hex}"

        if self._is_duplicate(unique_id):
            return self.async_abort(reason="already_configured")

        if user_input is not None and "name" in user_input:
            data: dict[str, Any] = {
                CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                CONF_TRANSMITTER_SERIAL: serial_hex,
                CONF_OPERATING_TYPE: "1",
                CONF_BUTTON_COUNT: self._button_count,
                CONF_GROUPING_MODE: self._grouping_mode,
                CONF_SWITCH_MODE: self._switch_mode,
            }
            return self._save_device(
                title=user_input["name"],
                unique_id=unique_id,
                data=data,
            )

        return self.async_show_form(
            step_id="transmitter_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "name",
                        default=self._next_default_name(ENTRY_TYPE_TRANSMITTER),
                    ): str,
                }
            ),
        )


class EasywaveConfigFlow(_EasywaveDeviceMixin, ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Easywave.

    - No existing gateway: walks through port selection and gateway setup.
    - Existing gateway present: shows the device-learning menu directly,
      allowing receivers, transmitters, and sensors to be
      added to the existing gateway from the 'Add entry' button.
    """

    VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._device: dict[str, Any] = {}
        self._existing_entry: ConfigEntry | None = None
        self._init_device_mixin()

    # ------------------------------------------------------------------
    # Mixin interface implementation
    # ------------------------------------------------------------------

    def _get_coordinator(self) -> Any | None:
        """Return the coordinator from the existing gateway entry."""
        entry = self._existing_entry
        if entry is not None and hasattr(entry, "runtime_data"):
            return entry.runtime_data.coordinator
        return None

    def _get_devices(self) -> list[dict[str, Any]]:
        """Return devices from the existing gateway entry options."""
        if self._existing_entry is not None:
            return list(self._existing_entry.options.get("devices", []))
        return []

    def _update_devices(self, devices: list[dict[str, Any]]) -> ConfigFlowResult:
        """Update the existing gateway options and finish the config flow."""
        assert self._existing_entry is not None
        self.hass.config_entries.async_update_entry(
            self._existing_entry,
            options={**self._existing_entry.options, "devices": devices},
        )
        return self.async_abort(reason="device_added")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Entry point.

        If an RX11 gateway is already configured, go straight to the
        device-learning menu instead of starting a new gateway setup.
        """
        existing = self.hass.config_entries.async_entries(DOMAIN)
        if existing:
            self._existing_entry = existing[0]
            return await self.async_step_init()
        return await self.async_step_ports()

    # ------------------------------------------------------------------
    # Gateway setup (reached only when no gateway exists yet)
    # ------------------------------------------------------------------

    async def async_step_ports(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show available serial ports and let the user pick one."""
        errors: dict[str, str] = {}
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
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

        if user_input is not None:
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

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._device["product"],
                "serial_number": serial_number,
                "device": self._device["device"],
            },
        )

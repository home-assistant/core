"""Sensor platform for the Easywave Core integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_STARTED,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EasywaveConfigEntry
from .const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
    EVENT_GATEWAY_CONNECTED,
    EVENT_GATEWAY_DISCONNECTED,
    EVENT_GATEWAY_STATUS_CHANGED,
    USB_DEVICE_NAMES,
)
from .coordinator import EasywaveCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave Core sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([EasywaveGatewaySensor(entry, coordinator)])


class EasywaveGatewaySensor(CoordinatorEntity[EasywaveCoordinator], SensorEntity):
    """Represents the RX11 USB gateway connectivity/state."""

    STATUS_KEYS = [
        "connected",
        "disconnected",
    ]

    _attr_has_entity_name = True
    _attr_translation_key = "gateway_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = STATUS_KEYS

    def __init__(self, entry: ConfigEntry, coordinator: EasywaveCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rx11_gateway"
        self._last_status = "disconnected"
        self._attr_icon = "mdi:close-thick"

        # Get USB device info — always use the canonical lookup table so
        # manufacturer/product stay in sync with const.py (the config entry
        # may still hold a stale value from the initial setup).
        vid: int | None = entry.data.get(CONF_USB_VID)
        pid: int | None = entry.data.get(CONF_USB_PID)
        device_entry = USB_DEVICE_NAMES.get((vid, pid)) if vid and pid else None

        # Use USB registry if available, fall back to entry config values
        if device_entry:
            self._usb_manufacturer = device_entry["manufacturer"]
            self._usb_product = device_entry["product"]
        else:
            self._usb_manufacturer = (
                entry.data.get(CONF_USB_MANUFACTURER) or "ELDAT EaS GmbH"
            )
            self._usb_product = (
                entry.data.get(CONF_USB_PRODUCT) or "Unknown Easywave Device"
            )

        # Prefer live transceiver serial/versions (already available after
        # coordinator.async_setup) over stale config entry values.
        transceiver = coordinator.transceiver
        self._usb_serial_number = transceiver.usb_serial_number or entry.data.get(
            CONF_USB_SERIAL_NUMBER, "unknown"
        )
        self._hw_version: str | None = transceiver.hw_version
        self._sw_version: str | None = transceiver.fw_version

        # Keep _current_status as None until EVENT_HOMEASSISTANT_STARTED so the
        # recorder/logbook can capture an initial "unknown" → "connected" transition
        # instead of leaving the last shutdown "unavailable" state as the latest entry.
        self._current_status: str | None = None

    def _connection_status(self) -> str:
        """Get connection status as constant key (translated by HA frontend).

        Returns the current connection status from the coordinator:
        - "connected": Device is currently connected
        - "disconnected": Device is not found or offline
        """
        # Check if device is offline (not found)
        if self.coordinator.is_offline:
            return "disconnected"

        # Check transceiver connection status
        transceiver = self.coordinator.transceiver
        if transceiver and transceiver.is_connected:
            return "connected"

        return "disconnected"

    @callback
    def _update_gateway_device_info(self) -> None:
        """Check if USB serial/version changed and update device registry.

        Updates local cached values from the transceiver and pushes changes
        to the Home Assistant device registry for persistence.
        """
        if self.coordinator.transceiver is None:
            return

        transceiver = self.coordinator.transceiver
        changed = False

        # Update serial number if transceiver reports a different one
        if (
            transceiver.usb_serial_number
            and transceiver.usb_serial_number != self._usb_serial_number
        ):
            self._usb_serial_number = transceiver.usb_serial_number
            changed = True

        # Update hardware/firmware versions if available
        if transceiver.hw_version and transceiver.hw_version != self._hw_version:
            self._hw_version = transceiver.hw_version
            changed = True
        if transceiver.fw_version and transceiver.fw_version != self._sw_version:
            self._sw_version = transceiver.fw_version
            changed = True

        if changed:
            # Push updated info to the device registry so the UI reflects
            # serial/version changes immediately (async_write_ha_state only
            # updates the entity state, not the device entry).
            registry = dr.async_get(self.hass)
            registry.async_get_or_create(
                config_entry_id=self._entry.entry_id,
                identifiers={(DOMAIN, f"{self._entry.entry_id}_gateway")},
                serial_number=self._usb_serial_number,
                hw_version=self._hw_version,
                sw_version=self._sw_version,
            )
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        new_status = self._connection_status()
        self._update_gateway_device_info()

        if new_status != self._last_status:
            old_status = self._last_status
            _LOGGER.info("Gateway status: %s -> %s", old_status, new_status)
            self._last_status = new_status

            registry = dr.async_get(self.hass)
            device = registry.async_get_device(
                identifiers={(DOMAIN, f"{self._entry.entry_id}_gateway")}
            )
            device_id = device.id if device is not None else None

            event_data = {
                "device_id": device_id,
                "old_status": old_status,
                "new_status": new_status,
                "entry_id": self._entry.entry_id,
            }
            self.hass.bus.async_fire(EVENT_GATEWAY_STATUS_CHANGED, event_data)
            if new_status == "connected":
                self.hass.bus.async_fire(EVENT_GATEWAY_CONNECTED, event_data)
            elif new_status == "disconnected":
                self.hass.bus.async_fire(EVENT_GATEWAY_DISCONNECTED, event_data)

        self._current_status = new_status
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to hass."""
        await super().async_added_to_hass()

        # Initialise last status.
        self._last_status = self._connection_status()

        # Write the correct state once HA has fully started so the recorder
        # captures a real unknown → connected transition.
        # native_value returns None until this fires (see _current_status).
        @callback
        def _on_ha_started(_event: Any = None) -> None:
            self._handle_coordinator_update()

        if self.hass.is_running:
            # Added while HA was already running (e.g. via UI config flow).
            # Defer by one event-loop tick so the entity is fully registered
            # in the state machine before the write.
            self.hass.loop.call_soon(_on_ha_started)
        else:
            # async_listen_once removes itself after firing — do NOT also wrap
            # with async_on_remove or HA raises ValueError on the double-remove.
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)

        # Listen for language/config changes to update translations dynamically.
        @callback
        def _handle_config_update(_event: Any) -> None:
            """Handle core config updates (including language changes)."""
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _handle_config_update)
        )

    @property
    def native_value(self) -> str | None:
        """Return connection status key - translated by frontend via translation_key.

        Returns None before EVENT_HOMEASSISTANT_STARTED so the
        recorder captures the state transition on first write.
        """
        return self._current_status

    @property
    def icon(self) -> str:
        """Return icon based on connection status."""
        if self._current_status == "connected":
            return "mdi:usb"
        # None / disconnected
        return "mdi:close-thick"

    @property
    def available(self) -> bool:
        """Gateway sensor is always available to show status."""
        # Gateway sensor should always be available so users can see the connection status.
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes with device details."""
        attrs = {
            "device_path": self._entry.data.get(CONF_DEVICE_PATH),
        }

        # Add serial number if available
        if self._usb_serial_number and self._usb_serial_number != "unknown":
            attrs["usb_serial_number"] = self._usb_serial_number

        # Add hardware version if available
        if self._hw_version and self._hw_version not in ("unknown", "error"):
            attrs["hardware_version"] = self._hw_version

        # Add firmware version if available
        if self._sw_version and self._sw_version not in ("unknown", "error"):
            attrs["firmware_version"] = self._sw_version

        # Add connection status
        attrs["connected"] = self._connection_status() == "connected"

        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the gateway."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_gateway")},
            name=self._usb_product,
            manufacturer=self._usb_manufacturer,
            model=self._usb_product,
            serial_number=(
                self._usb_serial_number
                if self._usb_serial_number != "unknown"
                else None
            ),
            hw_version=self._hw_version,
            sw_version=self._sw_version,
        )

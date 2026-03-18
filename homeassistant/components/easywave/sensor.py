"""Sensor platform for the Easywave Core integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Easywave Core sensors."""
    async_add_entities([EasywaveGatewaySensor(entry)])


class EasywaveGatewaySensor(SensorEntity):
    """Represents the RX11 USB gateway connectivity/state.

    For the CORE integration, stub methods are marked with # STUB.
    Replace the stub body to wire in live functionality once a
    transceiver object becomes available.
    """

    STATUS_KEYS = [
        "connected",
        "disconnected",
        "connecting",
        "error",
        "hardware_error",
        "not_configured",
    ]

    _attr_has_entity_name = True
    _attr_translation_key = "gateway_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = STATUS_KEYS

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rx11_gateway"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_options = self.STATUS_KEYS
        self._last_status = "disconnected"  # Default to disconnected
        self._attr_icon = "mdi:close-thick"  # Default icon for disconnected state

        # Get version info from transceiver (loaded at connect time).
        # STUB — no live transceiver in CORE; replace with real transceiver
        # reads (getattr(transceiver, '_hw_version', None) etc.) once available.
        self._hw_version: str | None = None
        self._sw_version: str | None = None

        # Get USB device info — always use the canonical lookup table so
        # manufacturer/product stay in sync with const.py (the config entry
        # may still hold a stale value from the initial setup).
        vid = entry.data.get(CONF_USB_VID)
        pid = entry.data.get(CONF_USB_PID)
        device_entry = USB_DEVICE_NAMES.get((vid, pid))
        
        # Use USB registry if available, fall back to entry config values
        if device_entry:
            self._usb_manufacturer = device_entry["manufacturer"]
            self._usb_product = device_entry["product"]
        else:
            self._usb_manufacturer = entry.data.get(CONF_USB_MANUFACTURER) or "ELDAT EaS GmbH"
            self._usb_product = entry.data.get(CONF_USB_PRODUCT) or "Unknown Easywave Device"
        self._usb_serial_number = entry.data.get(CONF_USB_SERIAL_NUMBER, "unknown")

        # CORE addition: _current_status stays None until EVENT_HOMEASSISTANT_STARTED
        # so the recorder captures a real unknown → connected transition (the
        # logbook would otherwise remain on the shutdown "unavailable" entry).
        self._current_status: str | None = None

    # ── Stub hooks ──────────────────────────────────────────────────────────

    def _get_connection_status_key(self) -> str:
        """Get connection status as constant key (translated by HA frontend).

        STUB — CORE has no rx-library transceiver; the RX11 is assumed
        connected whenever the integration is loaded.  Replace this body to
        read transceiver._rx11_wrapper._rx_module.connection_status and fall
        back to _is_connected() for full logic.
        """
        return "connected"

    def _is_connected(self) -> bool:
        """Return True when the gateway is reachable.

        STUB — always True in CORE; replace with:
            transceiver and hasattr(transceiver, 'is_connected') and transceiver.is_connected
        """
        return True

    @callback
    def _update_gateway_device_info(self) -> None:
        """Check if USB serial/version changed and update HA device registry.

        STUB — no-op in CORE because there is no live transceiver.
        Replace the body to read transceiver._hw_version / _fw_version,
        compare to cached values, and push changes to the device registry
        via dr.async_update_device() to enable live version tracking.
        """

    @callback
    def _handle_status_update(self) -> None:
        """Handle coordinator/status updates (including connection changes).

        Called from _on_ha_started, async_update, and — once a coordinator
        exists — registered via coordinator.async_add_listener().
        """
        new_status = self._get_connection_status_key()
        self._update_gateway_device_info()

        if new_status != self._last_status:
            old_status = self._last_status
            _LOGGER.info(
                "Gateway connection status changed: %s → %s", old_status, new_status
            )
            self._last_status = new_status

            event_data = {
                "device_id": f"{self._entry.entry_id}_gateway",
                "old_status": old_status,
                "new_status": new_status,
                "entry_id": self._entry.entry_id,
            }
            self.hass.bus.async_fire(EVENT_GATEWAY_STATUS_CHANGED, event_data)
            if new_status == "connected":
                self.hass.bus.async_fire(EVENT_GATEWAY_CONNECTED, event_data)
            elif new_status in ("disconnected", "error", "hardware_error"):
                self.hass.bus.async_fire(EVENT_GATEWAY_DISCONNECTED, event_data)

        self._current_status = new_status
        self.async_write_ha_state()

    # ── HA lifecycle ────────────────────────────────────────────────────────

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("Gateway sensor added with translation_key='gateway_status'")

        # Initialise last status.
        self._last_status = self._get_connection_status_key()

        # CORE addition: write the correct state once HA has fully started so
        # the recorder captures a real unknown → connected transition.
        # native_value returns None until this fires (see _current_status).
        @callback
        def _on_ha_started(_event: Any = None) -> None:
            self._handle_status_update()

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
            _LOGGER.debug("Core config updated, refreshing gateway sensor state")
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _handle_config_update)
        )

        # Register as listener with coordinator for immediate updates on
        # connection changes — wire in once a coordinator is available:
        #   self.async_on_remove(
        #       self.coordinator.async_add_listener(self._handle_status_update)
        #   )

    async def async_update(self) -> None:
        self._handle_status_update()

    # ── Entity properties ───────────────────────────────────────────────────

    @property
    def native_value(self) -> str | None:
        """Return connection status key - translated by frontend via translation_key.

        CORE addition: returns None before EVENT_HOMEASSISTANT_STARTED so the
        recorder captures the state transition on first write.
        """
        return self._current_status

    @property
    def icon(self) -> str:
        """Return icon based on connection status."""
        status = self._current_status
        if status == "connected":
            return "mdi:usb"
        elif status == "connecting":
            return "mdi:usb-flash-drive"
        elif status == "hardware_error":
            return "mdi:usb-port"
        elif status == "error":
            return "mdi:alert-circle"
        else:  # None / disconnected / not_configured
            return "mdi:close-thick"

    @property
    def available(self) -> bool:
        """Gateway sensor is always available to show status."""
        # Gateway sensor should always be available so users can see the connection status.
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "device_path": self._entry.data.get(CONF_DEVICE_PATH),
            "usb_serial_number": (
                self._usb_serial_number
                if self._usb_serial_number != "unknown"
                else None
            ),
            "hardware_version": self._hw_version,
            "firmware_version": self._sw_version,
            "connected": self._is_connected(),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info dynamically to support language changes."""
        # Get device info from USB_DEVICE_NAMES based on VID/PID
        vid = self._entry.data.get(CONF_USB_VID)
        pid = self._entry.data.get(CONF_USB_PID)
        device_entry = USB_DEVICE_NAMES.get((vid, pid))
        
        # Use USB registry if available, fall back to entry config values
        if device_entry:
            device_name = device_entry["product"]
            manufacturer = device_entry["manufacturer"]
        else:
            device_name = self._usb_product
            manufacturer = self._usb_manufacturer
        
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_gateway")},
            name=device_name,
            manufacturer=manufacturer,
            model=device_name,
            serial_number=(
                self._usb_serial_number
                if self._usb_serial_number != "unknown"
                else None
            ),
            hw_version=self._hw_version,
            sw_version=self._sw_version,
        )


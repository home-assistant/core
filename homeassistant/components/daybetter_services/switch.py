"""Support for DayBetter switches."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .daybetter_api import DayBetterApi
from .mqtt_manager import DayBetterMQTTManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up DayBetter switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    devices = data["devices"]

    # Ensure devices is a list, even if it's None
    if devices is None:
        devices = []

    _LOGGER.debug("Original devices list: %s", devices)

    # Remove duplicate devices based on deviceId and deviceName
    unique_devices = []
    seen_devices = set()

    for dev in devices:
        # Create a unique key based on deviceId and deviceName
        device_id = dev.get("deviceId")
        device_name = dev.get("deviceName")
        unique_key = (device_id, device_name)

        _LOGGER.debug("Processing device: %s (ID: %s)", device_name, device_id)

        # Only add device if we haven't seen this combination before
        if unique_key not in seen_devices:
            seen_devices.add(unique_key)
            unique_devices.append(dev)
            _LOGGER.debug("Added device: %s (ID: %s)", device_name, device_id)
        else:
            _LOGGER.debug(
                "Skipping duplicate device: %s (ID: %s)", device_name, device_id
            )

    _LOGGER.debug("Unique devices list: %s", unique_devices)

    # Get switch PIDs list
    pids_data = await api.fetch_pids()
    switch_pids_str = pids_data.get("switch", "")
    switch_pids = set(switch_pids_str.split(",")) if switch_pids_str else set()

    _LOGGER.debug("Switch PIDs string: %s", switch_pids_str)
    _LOGGER.debug("Switch PIDs set: %s", switch_pids)

    # Check if each device's deviceMoldPid is in switch_pids
    for dev in unique_devices:
        device_name = dev.get("deviceName", "unknown")
        device_mold_pid = dev.get("deviceMoldPid", "")
        is_switch = device_mold_pid in switch_pids
        _LOGGER.debug(
            "Device %s (PID: %s) is switch: %s", device_name, device_mold_pid, is_switch
        )

    # Restore PID filtering, only create real switch devices
    switches = [
        DayBetterSwitch(hass, api, dev, data.get("mqtt_manager"))
        for dev in unique_devices
        if dev.get("deviceMoldPid") in switch_pids
    ]

    _LOGGER.info("Created %d switch entities", len(switches))
    async_add_entities(switches)


class DayBetterSwitch(SwitchEntity):
    """Representation of a DayBetter switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DayBetterApi,
        device: dict[str, Any],
        mqtt_manager: DayBetterMQTTManager | None,
    ) -> None:
        """Initialize the switch."""
        self.hass = hass
        self._api = api
        self._device = device
        self._mqtt_manager = mqtt_manager
        self._attr_name = device.get("deviceGroupName", "DayBetter Switch")
        self._attr_unique_id = str(device.get("deviceName", "unknown"))
        self._is_on = device.get("deviceState", 0) == 1
        self._device_name = device.get("deviceName", "unknown")

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Register for MQTT updates if MQTT manager exists
        if self._mqtt_manager:
            # Register device switch status callback
            message_handler = self._mqtt_manager.get_message_handler()
            message_handler.register_device_switch_callback(
                self._handle_switch_status_update, self._device_name
            )

            # Listen to Home Assistant events
            self.async_on_remove(
                self.hass.bus.async_listen(
                    "daybetter_device_switch_changed", self._handle_switch_event
                )
            )

    @callback
    def _handle_switch_status_update(
        self, device_name: str, is_on: bool, device_type: int, topic: str
    ) -> None:
        """Handle switch status updates from MQTT."""
        _LOGGER.info(
            "🔄 Switch callback called: %s, current device: %s, status: %s",
            device_name,
            self._device_name,
            is_on,
        )
        if device_name == self._device_name:
            _LOGGER.info(
                "✅ Device name matches, updating status: %s -> %s", self._is_on, is_on
            )
            self._is_on = is_on
            _LOGGER.info("🔄 Calling async_write_ha_state()")
            self.async_write_ha_state()
            _LOGGER.info("✅ async_write_ha_state() call completed")
        else:
            _LOGGER.debug(
                "Device name doesn't match, skipping update: %s != %s",
                device_name,
                self._device_name,
            )

    @callback
    def _handle_switch_event(self, event) -> None:
        """Handle switch status events from Home Assistant."""
        try:
            event_data = event.data
            device_name = event_data.get("device_name")

            if device_name == self._device_name:
                is_on = event_data.get("is_on")
                _LOGGER.debug("Received switch event for %s: %s", device_name, is_on)
                self._is_on = is_on
                self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Error processing switch status event: %s", str(e))

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._is_on

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device.get("deviceId", "unknown"))},
            "name": self._attr_name,
            "manufacturer": "DayBetter",
            "model": self._device.get("deviceMoldPid", "Unknown"),
            "sw_version": self._device.get("swVersion", "Unknown"),
            "hw_version": self._device.get("hwVersion", "Unknown"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        result = await self._api.control_device(
            self._device["deviceName"], True, None, None, None
        )

        # Update status based on control results
        if result.get("code", 1):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        result = await self._api.control_device(
            self._device["deviceName"], False, None, None, None
        )

        # Update status based on control results
        if result.get("code", 1):
            self._is_on = False
            self.async_write_ha_state()

"""Component providing HA switch support for Ring Door Bell/Chimes."""
from datetime import timedelta
import logging
from typing import Any

import requests
from ring_doorbell import RingStickUpCam
from ring_doorbell.generic import RingGeneric

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN, RING_DEVICES, RING_DEVICES_COORDINATOR
from .coordinator import RingDataCoordinator
from .entity import RingEntity

_LOGGER = logging.getLogger(__name__)

SIREN_ICON = "mdi:alarm-bell"


# It takes a few seconds for the API to correctly return an update indicating
# that the changes have been made. Once we request a change (i.e. a light
# being turned on) we simply wait for this time delta before we allow
# updates to take place.

SKIP_UPDATES_DELAY = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the switches for the Ring devices."""
    devices = hass.data[DOMAIN][config_entry.entry_id][RING_DEVICES]
    coordinator: RingDataCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        RING_DEVICES_COORDINATOR
    ]
    switches = []

    for device in devices["stickup_cams"]:
        if device.has_capability("siren"):
            switches.append(SirenSwitch(device, coordinator))

    async_add_entities(switches)


class BaseRingSwitch(RingEntity, SwitchEntity):
    """Represents a switch for controlling an aspect of a ring device."""

    def __init__(
        self, device: RingGeneric, coordinator: RingDataCoordinator, device_type: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        self._device_type = device_type
        self._attr_unique_id = f"{self._device.id}-{self._device_type}"


class SirenSwitch(BaseRingSwitch):
    """Creates a switch to turn the ring cameras siren on and off."""

    _attr_translation_key = "siren"
    _attr_icon = SIREN_ICON

    def __init__(self, device: RingGeneric, coordinator: RingDataCoordinator) -> None:
        """Initialize the switch for a device with a siren."""
        super().__init__(device, coordinator, "siren")
        self._no_updates_until = dt_util.utcnow()
        self._attr_is_on = device.siren > 0

    @callback
    def _handle_coordinator_update(self):
        """Call update method."""
        if self._no_updates_until > dt_util.utcnow():
            return

        if (device := self._get_coordinator_device()) and isinstance(
            device, RingStickUpCam
        ):
            self._attr_is_on = device.siren > 0
        super()._handle_coordinator_update()

    def _set_switch(self, new_state):
        """Update switch state, and causes Home Assistant to correctly update."""
        try:
            self._device.siren = new_state
        except requests.Timeout:
            _LOGGER.error("Time out setting %s siren to %s", self.entity_id, new_state)
            return

        self._attr_is_on = new_state > 0
        self._no_updates_until = dt_util.utcnow() + SKIP_UPDATES_DELAY
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on for 30 seconds."""
        self._set_switch(1)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        self._set_switch(0)

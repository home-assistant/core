"""Component providing HA switch support for Ring Door Bell/Chimes."""
from datetime import timedelta
import logging
from typing import Any

import requests
from ring_doorbell import RingStickUpCam
from ring_doorbell.generic import RingGeneric

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN, RING_DEVICES, RING_DEVICES_COORDINATOR
from .coordinator import RingDataCoordinator
from .entity import RingEntity

_LOGGER = logging.getLogger(__name__)


# It takes a few seconds for the API to correctly return an update indicating
# that the changes have been made. Once we request a change (i.e. a light
# being turned on) we simply wait for this time delta before we allow
# updates to take place.

SKIP_UPDATES_DELAY = timedelta(seconds=5)

ON_STATE = "on"
OFF_STATE = "off"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the lights for the Ring devices."""
    devices = hass.data[DOMAIN][config_entry.entry_id][RING_DEVICES]
    devices_coordinator: RingDataCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        RING_DEVICES_COORDINATOR
    ]
    lights = []

    for device in devices["stickup_cams"]:
        if device.has_capability("light"):
            lights.append(RingLight(device, devices_coordinator))

    async_add_entities(lights)


class RingLight(RingEntity, LightEntity):
    """Creates a switch to turn the ring cameras light on and off."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "light"

    def __init__(self, device: RingGeneric, coordinator) -> None:
        """Initialize the light."""
        super().__init__(device, coordinator)
        self._attr_unique_id = device.id
        self._attr_is_on = device.lights == ON_STATE
        self._no_updates_until = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self):
        """Call update method."""
        if self._no_updates_until > dt_util.utcnow():
            return
        if (device := self._get_coordinator_device()) and isinstance(
            device, RingStickUpCam
        ):
            self._attr_is_on = device.lights == ON_STATE
        super()._handle_coordinator_update()

    def _set_light(self, new_state):
        """Update light state, and causes Home Assistant to correctly update."""
        try:
            self._device.lights = new_state
        except requests.Timeout:
            _LOGGER.error("Time out setting %s light to %s", self.entity_id, new_state)
            return

        self._attr_is_on = new_state == ON_STATE
        self._no_updates_until = dt_util.utcnow() + SKIP_UPDATES_DELAY
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on for 30 seconds."""
        self._set_light(ON_STATE)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._set_light(OFF_STATE)

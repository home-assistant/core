"""Component providing HA switch support for Ring Door Bell/Chimes."""

from datetime import timedelta
from enum import StrEnum, auto
import logging
from typing import Any

from ring_doorbell import RingStickUpCam

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import RingConfigEntry
from .coordinator import RingDataCoordinator
from .entity import RingEntity, exception_wrap

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
# Actions restricted to 1 at a time
PARALLEL_UPDATES = 1

# It takes a few seconds for the API to correctly return an update indicating
# that the changes have been made. Once we request a change (i.e. a light
# being turned on) we simply wait for this time delta before we allow
# updates to take place.

SKIP_UPDATES_DELAY = timedelta(seconds=5)


class OnOffState(StrEnum):
    """Enum for allowed on off states."""

    ON = auto()
    OFF = auto()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the lights for the Ring devices."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator

    async_add_entities(
        RingLight(device, devices_coordinator)
        for device in ring_data.devices.stickup_cams
        if device.has_capability("light")
    )


class RingLight(RingEntity[RingStickUpCam], LightEntity):
    """Creates a switch to turn the ring cameras light on and off."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "light"

    def __init__(
        self, device: RingStickUpCam, coordinator: RingDataCoordinator
    ) -> None:
        """Initialize the light."""
        super().__init__(device, coordinator)
        self._attr_unique_id = str(device.id)
        self._attr_is_on = device.lights == OnOffState.ON
        self._no_updates_until = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Call update method."""
        if self._no_updates_until > dt_util.utcnow():
            return
        device = self._get_coordinator_data().get_stickup_cam(
            self._device.device_api_id
        )
        self._attr_is_on = device.lights == OnOffState.ON
        super()._handle_coordinator_update()

    @exception_wrap
    async def _async_set_light(self, new_state: OnOffState) -> None:
        """Update light state, and causes Home Assistant to correctly update."""
        await self._device.async_set_lights(new_state)

        self._attr_is_on = new_state == OnOffState.ON
        self._no_updates_until = dt_util.utcnow() + SKIP_UPDATES_DELAY
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on for 30 seconds."""
        await self._async_set_light(OnOffState.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_set_light(OnOffState.OFF)

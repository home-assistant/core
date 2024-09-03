"""Component providing HA switch support for Ring Door Bell/Chimes."""

from datetime import timedelta
import logging
from typing import Any

from ring_doorbell import RingStickUpCam

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import RingConfigEntry
from .coordinator import RingDataCoordinator
from .entity import RingEntity, exception_wrap

_LOGGER = logging.getLogger(__name__)


# It takes a few seconds for the API to correctly return an update indicating
# that the changes have been made. Once we request a change (i.e. a light
# being turned on) we simply wait for this time delta before we allow
# updates to take place.

SKIP_UPDATES_DELAY = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the switches for the Ring devices."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator

    async_add_entities(
        SirenSwitch(device, devices_coordinator)
        for device in ring_data.devices.stickup_cams
        if device.has_capability("siren")
    )


class BaseRingSwitch(RingEntity[RingStickUpCam], SwitchEntity):
    """Represents a switch for controlling an aspect of a ring device."""

    def __init__(
        self, device: RingStickUpCam, coordinator: RingDataCoordinator, device_type: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        self._device_type = device_type
        self._attr_unique_id = f"{self._device.id}-{self._device_type}"


class SirenSwitch(BaseRingSwitch):
    """Creates a switch to turn the ring cameras siren on and off."""

    _attr_translation_key = "siren"

    def __init__(
        self, device: RingStickUpCam, coordinator: RingDataCoordinator
    ) -> None:
        """Initialize the switch for a device with a siren."""
        super().__init__(device, coordinator, "siren")
        self._no_updates_until = dt_util.utcnow()
        self._attr_is_on = device.siren > 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Call update method."""
        if self._no_updates_until > dt_util.utcnow():
            return
        device = self._get_coordinator_data().get_stickup_cam(
            self._device.device_api_id
        )
        self._attr_is_on = device.siren > 0
        super()._handle_coordinator_update()

    @exception_wrap
    async def _async_set_switch(self, new_state: int) -> None:
        """Update switch state, and causes Home Assistant to correctly update."""
        await self._device.async_set_siren(new_state)

        self._attr_is_on = new_state > 0
        self._no_updates_until = dt_util.utcnow() + SKIP_UPDATES_DELAY
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on for 30 seconds."""
        await self._async_set_switch(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        await self._async_set_switch(0)

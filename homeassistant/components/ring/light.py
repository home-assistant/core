"""Component providing HA switch support for Ring Door Bell/Chimes."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum, auto
import logging
from typing import Any

from ring_doorbell import RingCapability, RingStickUpCam

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import RingConfigEntry
from .coordinator import RingDataCoordinator
from .entity import RingDeviceT, RingEntity, RingEntityDescription, exception_wrap

_LOGGER = logging.getLogger(__name__)


# It takes a few seconds for the API to correctly return an update indicating
# that the changes have been made. Once we request a change (i.e. a light
# being turned on) we simply wait for this time delta before we allow
# updates to take place.

SKIP_UPDATES_DELAY = timedelta(seconds=5)


@dataclass(frozen=True, kw_only=True)
class RingLightEntityDescription(
    LightEntityDescription, RingEntityDescription[RingDeviceT]
):
    """Describes a Ring light entity."""


LIGHTS: Iterable[RingLightEntityDescription] = (
    RingLightEntityDescription(
        key="light",
        translation_key="light",
        exists_fn=lambda device: device.has_capability(RingCapability.LIGHT),
        unique_id_fn=lambda _, device: f"{device.device_api_id}",
    ),
)


class OnOffState(StrEnum):
    """Enum for allowed on off states."""

    ON = auto()
    OFF = auto()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the lights for the Ring devices."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator

    RingLight.process_entities(
        hass,
        devices_coordinator,
        entry=entry,
        async_add_entities=async_add_entities,
        domain=LIGHT_DOMAIN,
        descriptions=LIGHTS,
    )


class RingLight(RingEntity[RingStickUpCam], LightEntity):
    """Creates a switch to turn the ring cameras light on and off."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        device: RingStickUpCam,
        coordinator: RingDataCoordinator,
        description: RingLightEntityDescription[RingStickUpCam],
    ) -> None:
        """Initialize the light."""
        super().__init__(device, coordinator, description)
        self._attr_is_on = device.lights == OnOffState.ON
        self._no_updates_until = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Call update method."""
        if self._removed:
            return
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

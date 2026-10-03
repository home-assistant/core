"""Component providing HA switch support for Ring Door Bell/Chimes."""

from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass
import logging
from typing import Any, Generic, Self, cast, override

from ring_doorbell import RingCapability, RingDoorBell, RingStickUpCam
from ring_doorbell.const import DOORBELL_EXISTING_TYPE

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import RingConfigEntry
from .const import DOMAIN
from .coordinator import RingDataCoordinator
from .entity import (
    DeprecatedInfo,
    RingDeviceT,
    RingEntity,
    RingEntityDescription,
    async_check_create_deprecated,
    refresh_after,
)

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
# Actions restricted to 1 at a time
PARALLEL_UPDATES = 1

IN_HOME_CHIME_IS_PRESENT = {v for k, v in DOORBELL_EXISTING_TYPE.items() if k != 2}


def _in_home_chime_exists(device: RingDoorBell) -> bool:
    """Return True if the doorbell has an in-home chime."""
    if device.family != "doorbots":
        return False
    try:
        return device.existing_doorbell_type in IN_HOME_CHIME_IS_PRESENT
    except KeyError as ex:
        _LOGGER.debug(
            "Unknown doorbell chime type %s; skipping in-home chime for %s",
            ex,
            device.device_api_id,
        )
        return False


def _in_home_chime_is_on(device: RingDoorBell) -> bool | None:
    """Return if the in-home chime is enabled; None when the chime type is unknown."""
    try:
        return device.existing_doorbell_type_enabled or False
    except KeyError:
        return None


async def _async_set_in_home_chime_enabled(device: RingDoorBell, enabled: bool) -> None:
    """Enable or disable the in-home chime."""
    try:
        await device.async_set_existing_doorbell_type_enabled(enabled)
    except KeyError as ex:
        _LOGGER.debug("In-home chime type unknown for %s", device.device_api_id)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="chime_type_unknown"
        ) from ex


@dataclass(frozen=True, kw_only=True)
class RingSwitchEntityDescription(
    SwitchEntityDescription,
    RingEntityDescription,
    Generic[RingDeviceT],  # noqa: UP046
):
    """Describes a Ring switch entity."""

    exists_fn: Callable[[RingDeviceT], bool]
    unique_id_fn: Callable[[Self, RingDeviceT], str] = lambda self, device: (
        f"{device.device_api_id}-{self.key}"
    )
    is_on_fn: Callable[[RingDeviceT], bool | None]
    turn_on_fn: Callable[[RingDeviceT], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[RingDeviceT], Coroutine[Any, Any, None]]


SWITCHES: Sequence[RingSwitchEntityDescription[Any]] = (
    RingSwitchEntityDescription[RingStickUpCam](
        key="siren",
        translation_key="siren",
        exists_fn=lambda device: device.has_capability(RingCapability.SIREN),
        is_on_fn=lambda device: device.siren > 0,
        turn_on_fn=lambda device: device.async_set_siren(1),
        turn_off_fn=lambda device: device.async_set_siren(0),
        deprecated_info=DeprecatedInfo(
            new_platform=Platform.SIREN, breaks_in_ha_version="2025.4.0"
        ),
    ),
    RingSwitchEntityDescription[RingDoorBell](
        key="in_home_chime",
        translation_key="in_home_chime",
        exists_fn=_in_home_chime_exists,
        is_on_fn=_in_home_chime_is_on,
        turn_on_fn=lambda device: _async_set_in_home_chime_enabled(device, True),
        turn_off_fn=lambda device: _async_set_in_home_chime_enabled(device, False),
    ),
    RingSwitchEntityDescription[RingDoorBell](
        key="motion_detection",
        translation_key="motion_detection",
        exists_fn=lambda device: device.has_capability(RingCapability.MOTION_DETECTION),
        is_on_fn=lambda device: device.motion_detection,
        turn_on_fn=lambda device: device.async_set_motion_detection(True),
        turn_off_fn=lambda device: device.async_set_motion_detection(False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the switches for the Ring devices."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator

    async_add_entities(
        RingSwitch(device, devices_coordinator, description)
        for description in SWITCHES
        for device in ring_data.devices.all_devices
        if description.exists_fn(device)
        and async_check_create_deprecated(
            hass,
            Platform.SWITCH,
            description.unique_id_fn(description, device),
            description,
        )
    )


class RingSwitch(RingEntity[RingDeviceT], SwitchEntity):
    """Represents a switch for controlling an aspect of a ring device."""

    entity_description: RingSwitchEntityDescription[RingDeviceT]

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: RingDataCoordinator,
        description: RingSwitchEntityDescription[RingDeviceT],
    ) -> None:
        """Initialize the switch."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._no_updates_until = dt_util.utcnow()
        self._attr_unique_id = description.unique_id_fn(description, device)
        self._attr_is_on = description.is_on_fn(device)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Call update method."""
        self._device = cast(
            RingDeviceT,
            self._get_coordinator_data().get_device(self._device.device_api_id),
        )
        self._attr_is_on = self.entity_description.is_on_fn(self._device)
        super()._handle_coordinator_update()

    @refresh_after
    async def _async_set_switch(self, switch_on: bool) -> None:
        """Update switch state, and causes Home Assistant to correctly update."""
        if switch_on:
            await self.entity_description.turn_on_fn(self._device)
        else:
            await self.entity_description.turn_off_fn(self._device)

        self._attr_is_on = switch_on
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on for 30 seconds."""
        await self._async_set_switch(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        await self._async_set_switch(False)

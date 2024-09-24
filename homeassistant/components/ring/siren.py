"""Component providing HA Siren support for Ring Chimes."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Generic, cast

from ring_doorbell import (
    RingCapability,
    RingChime,
    RingEventKind,
    RingGeneric,
    RingStickUpCam,
)

from homeassistant.components.siren import (
    ATTR_TONE,
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
    SirenTurnOnServiceParameters,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RingConfigEntry
from .coordinator import RingDataCoordinator
from .entity import (
    RingDeviceT,
    RingEntity,
    RingEntityDescription,
    async_check_create_deprecated,
    refresh_after,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RingSirenEntityDescription(
    SirenEntityDescription, RingEntityDescription, Generic[RingDeviceT]
):
    """Describes a Ring siren entity."""

    exists_fn: Callable[[RingGeneric], bool]
    unique_id_fn: Callable[[RingDeviceT], str] = lambda device: str(
        device.device_api_id
    )
    is_on_fn: Callable[[RingDeviceT], bool] | None = None
    turn_on_fn: (
        Callable[[RingDeviceT, SirenTurnOnServiceParameters], Coroutine[Any, Any, Any]]
        | None
    ) = None
    turn_off_fn: Callable[[RingDeviceT], Coroutine[Any, Any, None]] | None = None


SIRENS: tuple[RingSirenEntityDescription[Any], ...] = (
    RingSirenEntityDescription[RingChime](
        key="siren",
        translation_key="siren",
        available_tones=[RingEventKind.DING.value, RingEventKind.MOTION.value],
        # Historically the chime siren entity has appended `siren` to the unique id
        unique_id_fn=lambda device: f"{device.device_api_id}-siren",
        exists_fn=lambda device: isinstance(device, RingChime),
        turn_on_fn=lambda device, kwargs: device.async_test_sound(
            kind=str(kwargs.get(ATTR_TONE) or "") or RingEventKind.DING.value
        ),
    ),
    RingSirenEntityDescription[RingStickUpCam](
        key="siren",
        translation_key="siren",
        exists_fn=lambda device: device.has_capability(RingCapability.SIREN),
        is_on_fn=lambda device: device.siren > 0,
        turn_on_fn=lambda device, _: device.async_set_siren(1),
        turn_off_fn=lambda device: device.async_set_siren(0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sirens for the Ring devices."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator

    async_add_entities(
        RingSiren(device, devices_coordinator, description)
        for device in ring_data.devices.all_devices
        for description in SIRENS
        if description.exists_fn(device)
        and async_check_create_deprecated(
            hass,
            Platform.SIREN,
            description.unique_id_fn(device),
            description,
        )
    )


class RingSiren(RingEntity[RingDeviceT], SirenEntity):
    """Creates a siren to play the test chimes of a Chime device."""

    entity_description: RingSirenEntityDescription[RingDeviceT]

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: RingDataCoordinator,
        description: RingSirenEntityDescription[RingDeviceT],
    ) -> None:
        """Initialize a Ring Chime siren."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = description.unique_id_fn(device)
        if description.is_on_fn:
            self._attr_is_on = description.is_on_fn(self._device)
        features = SirenEntityFeature(0)
        if description.turn_on_fn:
            features = features | SirenEntityFeature.TURN_ON
        if description.turn_off_fn:
            features = features | SirenEntityFeature.TURN_OFF
        if description.available_tones:
            features = features | SirenEntityFeature.TONES
        self._attr_supported_features = features

    async def _async_set_siren(self, siren_on: bool, **kwargs: Any) -> None:
        if siren_on and self.entity_description.turn_on_fn:
            turn_on_params = cast(SirenTurnOnServiceParameters, kwargs)
            await self.entity_description.turn_on_fn(self._device, turn_on_params)
        elif not siren_on and self.entity_description.turn_off_fn:
            await self.entity_description.turn_off_fn(self._device)

        if self.entity_description.is_on_fn:
            self._attr_is_on = siren_on
            self.async_write_ha_state()

    @refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the siren."""
        await self._async_set_siren(True, **kwargs)

    @refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the siren."""
        await self._async_set_siren(False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Call update method."""
        if not self.entity_description.is_on_fn:
            return
        self._device = cast(
            RingDeviceT,
            self._get_coordinator_data().get_device(self._device.device_api_id),
        )
        self._attr_is_on = self.entity_description.is_on_fn(self._device)
        super()._handle_coordinator_update()

"""Component providing HA number support for Ring Door Bell/Chimes."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, cast

from ring_doorbell import RingChime, RingDoorBell, RingGeneric, RingOther
import ring_doorbell.const

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RingConfigEntry
from .coordinator import RingDataCoordinator
from .entity import RingDeviceT, RingEntity, refresh_after

# Coordinator is used to centralize the data updates
# Actions restricted to 1 at a time
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a numbers for a Ring device."""
    ring_data = entry.runtime_data
    devices_coordinator = ring_data.devices_coordinator

    async_add_entities(
        RingNumber(device, devices_coordinator, description)
        for description in NUMBER_TYPES
        for device in ring_data.devices.all_devices
        if description.exists_fn(device)
    )


@dataclass(frozen=True, kw_only=True)
class RingNumberEntityDescription(NumberEntityDescription, Generic[RingDeviceT]):
    """Describes Ring number entity."""

    value_fn: Callable[[RingDeviceT], StateType]
    setter_fn: Callable[[RingDeviceT, float], Awaitable[None]]
    exists_fn: Callable[[RingGeneric], bool]


NUMBER_TYPES: tuple[RingNumberEntityDescription[Any], ...] = (
    RingNumberEntityDescription[RingChime](
        key="volume",
        translation_key="volume",
        mode=NumberMode.SLIDER,
        native_min_value=ring_doorbell.const.CHIME_VOL_MIN,
        native_max_value=ring_doorbell.const.CHIME_VOL_MAX,
        native_step=1,
        value_fn=lambda device: device.volume,
        setter_fn=lambda device, value: device.async_set_volume(int(value)),
        exists_fn=lambda device: isinstance(device, RingChime),
    ),
    RingNumberEntityDescription[RingDoorBell](
        key="volume",
        translation_key="volume",
        mode=NumberMode.SLIDER,
        native_min_value=ring_doorbell.const.DOORBELL_VOL_MIN,
        native_max_value=ring_doorbell.const.DOORBELL_VOL_MAX,
        native_step=1,
        value_fn=lambda device: device.volume,
        setter_fn=lambda device, value: device.async_set_volume(int(value)),
        exists_fn=lambda device: isinstance(device, RingDoorBell),
    ),
    RingNumberEntityDescription[RingOther](
        key="doorbell_volume",
        translation_key="doorbell_volume",
        mode=NumberMode.SLIDER,
        native_min_value=ring_doorbell.const.OTHER_DOORBELL_VOL_MIN,
        native_max_value=ring_doorbell.const.OTHER_DOORBELL_VOL_MAX,
        native_step=1,
        value_fn=lambda device: device.doorbell_volume,
        setter_fn=lambda device, value: device.async_set_doorbell_volume(int(value)),
        exists_fn=lambda device: isinstance(device, RingOther),
    ),
    RingNumberEntityDescription[RingOther](
        key="mic_volume",
        translation_key="mic_volume",
        mode=NumberMode.SLIDER,
        native_min_value=ring_doorbell.const.MIC_VOL_MIN,
        native_max_value=ring_doorbell.const.MIC_VOL_MAX,
        native_step=1,
        value_fn=lambda device: device.mic_volume,
        setter_fn=lambda device, value: device.async_set_mic_volume(int(value)),
        exists_fn=lambda device: isinstance(device, RingOther),
    ),
    RingNumberEntityDescription[RingOther](
        key="voice_volume",
        translation_key="voice_volume",
        mode=NumberMode.SLIDER,
        native_min_value=ring_doorbell.const.VOICE_VOL_MIN,
        native_max_value=ring_doorbell.const.VOICE_VOL_MAX,
        native_step=1,
        value_fn=lambda device: device.voice_volume,
        setter_fn=lambda device, value: device.async_set_voice_volume(int(value)),
        exists_fn=lambda device: isinstance(device, RingOther),
    ),
)


class RingNumber(RingEntity[RingDeviceT], NumberEntity):
    """A number implementation for Ring device."""

    entity_description: RingNumberEntityDescription[RingDeviceT]

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: RingDataCoordinator,
        description: RingNumberEntityDescription[RingDeviceT],
    ) -> None:
        """Initialize a number for Ring device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}-{description.key}"
        self._update_native_value()

    def _update_native_value(self) -> None:
        native_value = self.entity_description.value_fn(self._device)
        if native_value is not None:
            self._attr_native_value = float(native_value)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Call update method."""

        self._device = cast(
            RingDeviceT,
            self._get_coordinator_data().get_device(self._device.device_api_id),
        )

        self._update_native_value()

        super()._handle_coordinator_update()

    @refresh_after
    async def async_set_native_value(self, value: float) -> None:
        """Call setter on Ring device."""
        await self.entity_description.setter_fn(self._device, value)

        self._attr_native_value = value
        self.async_write_ha_state()

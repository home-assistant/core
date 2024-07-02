"""Component providing HA sensor support for Ring Door Bell/Chimes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, cast

from ring_doorbell import (
    RingCapability,
    RingChime,
    RingDoorBell,
    RingEventKind,
    RingGeneric,
    RingOther,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RingData
from .const import DOMAIN
from .coordinator import RingDataCoordinator
from .entity import RingDeviceT, RingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a sensor for a Ring device."""
    ring_data: RingData = hass.data[DOMAIN][config_entry.entry_id]
    devices_coordinator = ring_data.devices_coordinator

    entities = [
        RingSensor(device, devices_coordinator, description)
        for description in SENSOR_TYPES
        for device in ring_data.devices.all_devices
        if description.exists_fn(device)
    ]

    async_add_entities(entities)


class RingSensor(RingEntity[RingDeviceT], SensorEntity):
    """A sensor implementation for Ring device."""

    entity_description: RingSensorEntityDescription[RingDeviceT]

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: RingDataCoordinator,
        description: RingSensorEntityDescription[RingDeviceT],
    ) -> None:
        """Initialize a sensor for Ring device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}-{description.key}"
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        self._attr_native_value = self.entity_description.value_fn(self._device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Call update method."""

        self._device = cast(
            RingDeviceT,
            self._get_coordinator_data().get_device(self._device.device_api_id),
        )
        # History values can drop off the last 10 events so only update
        # the value if it's not None
        if native_value := self.entity_description.value_fn(self._device):
            self._attr_native_value = native_value
        if extra_attrs := self.entity_description.extra_state_attributes_fn(
            self._device
        ):
            self._attr_extra_state_attributes = extra_attrs
        super()._handle_coordinator_update()


def _get_last_event(
    history_data: list[dict[str, Any]], kind: RingEventKind | None
) -> dict[str, Any] | None:
    if not history_data:
        return None
    if kind is None:
        return history_data[0]
    for entry in history_data:
        if entry["kind"] == kind.value:
            return entry
    return None


def _get_last_event_attrs(
    history_data: list[dict[str, Any]], kind: RingEventKind | None
) -> dict[str, Any] | None:
    if last_event := _get_last_event(history_data, kind):
        return {
            "created_at": last_event.get("created_at"),
            "answered": last_event.get("answered"),
            "recording_status": last_event.get("recording", {}).get("status"),
            "category": last_event.get("kind"),
        }
    return None


@dataclass(frozen=True, kw_only=True)
class RingSensorEntityDescription(SensorEntityDescription, Generic[RingDeviceT]):
    """Describes Ring sensor entity."""

    value_fn: Callable[[RingDeviceT], StateType] = lambda _: True
    exists_fn: Callable[[RingGeneric], bool] = lambda _: True
    extra_state_attributes_fn: Callable[[RingDeviceT], dict[str, Any] | None] = (
        lambda _: None
    )


# For some reason mypy doesn't properly type check the default TypeVar value here
# so for now the [RingGeneric] subscript needs to be specified.
# Once https://github.com/python/mypy/issues/14851 is closed this should hopefully
# be fixed and the [RingGeneric] subscript can be removed.
# https://github.com/home-assistant/core/pull/115276#discussion_r1560106576
SENSOR_TYPES: tuple[RingSensorEntityDescription[Any], ...] = (
    RingSensorEntityDescription[RingGeneric](
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.battery_life,
        exists_fn=lambda device: device.family != "chimes",
    ),
    RingSensorEntityDescription[RingGeneric](
        key="last_activity",
        translation_key="last_activity",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: last_event.get("created_at")
        if (last_event := _get_last_event(device.last_history, None))
        else None,
        extra_state_attributes_fn=lambda device: last_event_attrs
        if (last_event_attrs := _get_last_event_attrs(device.last_history, None))
        else None,
        exists_fn=lambda device: device.has_capability(RingCapability.HISTORY),
    ),
    RingSensorEntityDescription[RingGeneric](
        key="last_ding",
        translation_key="last_ding",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: last_event.get("created_at")
        if (last_event := _get_last_event(device.last_history, RingEventKind.DING))
        else None,
        extra_state_attributes_fn=lambda device: last_event_attrs
        if (
            last_event_attrs := _get_last_event_attrs(
                device.last_history, RingEventKind.DING
            )
        )
        else None,
        exists_fn=lambda device: device.has_capability(RingCapability.HISTORY),
    ),
    RingSensorEntityDescription[RingGeneric](
        key="last_motion",
        translation_key="last_motion",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: last_event.get("created_at")
        if (last_event := _get_last_event(device.last_history, RingEventKind.MOTION))
        else None,
        extra_state_attributes_fn=lambda device: last_event_attrs
        if (
            last_event_attrs := _get_last_event_attrs(
                device.last_history, RingEventKind.MOTION
            )
        )
        else None,
        exists_fn=lambda device: device.has_capability(RingCapability.HISTORY),
    ),
    RingSensorEntityDescription[RingDoorBell | RingChime](
        key="volume",
        translation_key="volume",
        value_fn=lambda device: device.volume,
        exists_fn=lambda device: isinstance(device, (RingDoorBell, RingChime)),
    ),
    RingSensorEntityDescription[RingOther](
        key="doorbell_volume",
        translation_key="doorbell_volume",
        value_fn=lambda device: device.doorbell_volume,
        exists_fn=lambda device: isinstance(device, RingOther),
    ),
    RingSensorEntityDescription[RingOther](
        key="mic_volume",
        translation_key="mic_volume",
        value_fn=lambda device: device.mic_volume,
        exists_fn=lambda device: isinstance(device, RingOther),
    ),
    RingSensorEntityDescription[RingOther](
        key="voice_volume",
        translation_key="voice_volume",
        value_fn=lambda device: device.voice_volume,
        exists_fn=lambda device: isinstance(device, RingOther),
    ),
    RingSensorEntityDescription[RingGeneric](
        key="wifi_signal_category",
        translation_key="wifi_signal_category",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.wifi_signal_category,
    ),
    RingSensorEntityDescription[RingGeneric](
        key="wifi_signal_strength",
        translation_key="wifi_signal_strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.wifi_signal_strength,
    ),
)

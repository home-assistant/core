"""Binary sensor platform for the Place integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from place.models.device_shadow import AlarmStatus, PlaceDeviceShadow
from place.models.discover_device import DiscoverDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlaceConfigEntry, PlaceCoordinator

PARALLEL_UPDATES = 0

ALARM_ON_STATES = frozenset({AlarmStatus.ALARM, AlarmStatus.CRITICAL_ALARM})


@dataclass(frozen=True, kw_only=True)
class PlaceAlarmBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Place alarm binary sensor."""

    value_fn: Callable[[PlaceDeviceShadow], AlarmStatus]


ALARM_BINARY_SENSOR_DESCRIPTIONS: tuple[
    PlaceAlarmBinarySensorEntityDescription, ...
] = (
    PlaceAlarmBinarySensorEntityDescription(
        key="co_alarm",
        device_class=BinarySensorDeviceClass.CO,
        value_fn=lambda shadow: shadow.co_alarm_status,
    ),
    PlaceAlarmBinarySensorEntityDescription(
        key="heat_alarm",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda shadow: shadow.heat_alarm_status,
    ),
    PlaceAlarmBinarySensorEntityDescription(
        key="smoke_alarm",
        device_class=BinarySensorDeviceClass.SMOKE,
        value_fn=lambda shadow: shadow.smoke_alarm_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Place alarm binary sensor entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        PlaceAlarmBinarySensorEntity(coordinator, device, description)
        for device in coordinator.devices
        if device.thing_name
        for description in ALARM_BINARY_SENSOR_DESCRIPTIONS
    )


class PlaceAlarmBinarySensorEntity(
    CoordinatorEntity[PlaceCoordinator], BinarySensorEntity
):
    """Binary sensor that is on when a Place alarm is actively triggered."""

    _attr_has_entity_name = True

    entity_description: PlaceAlarmBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PlaceCoordinator,
        device: DiscoverDevice,
        description: PlaceAlarmBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._thing_name: str = device.thing_name
        self._device_name: str = (
            device.location or device.device_name or device.device_id
        )
        self.entity_description = description
        self._attr_unique_id = f"{self._thing_name}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._thing_name)},
            name=self._device_name,
            manufacturer="Gentex",
            model=device.model_number,
            sw_version=device.firmware_version,
        )

    def _shadow(self) -> PlaceDeviceShadow | None:
        """Return the current shadow for this device, if any."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._thing_name)

    @property
    @override
    def available(self) -> bool:
        """Unavailable when the device does not have this alarm type."""
        if not super().available:
            return False
        shadow = self._shadow()
        if shadow is None:
            return True
        return self.entity_description.value_fn(shadow) is not AlarmStatus.NOT_PRESENT

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true when the alarm is in an active (dangerous) state."""
        shadow = self._shadow()
        if shadow is None:
            return None
        return self.entity_description.value_fn(shadow) in ALARM_ON_STATES

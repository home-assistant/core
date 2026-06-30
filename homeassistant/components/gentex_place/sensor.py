"""Sensor platform for the Place integration."""

from collections.abc import Callable
from dataclasses import dataclass

from place.models.device_shadow import AlarmStatus, PlaceDeviceShadow
from place.models.discover_device import DiscoverDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlaceConfigEntry, PlaceCoordinator

ALARM_STATUS_OPTIONS = [status.name.lower() for status in AlarmStatus]


@dataclass(frozen=True, kw_only=True)
class PlaceAlarmSensorEntityDescription(SensorEntityDescription):
    """Describe a Place alarm sensor."""

    value_fn: Callable[[PlaceDeviceShadow], AlarmStatus]


ALARM_SENSOR_DESCRIPTIONS: tuple[PlaceAlarmSensorEntityDescription, ...] = (
    PlaceAlarmSensorEntityDescription(
        key="co_alarm_status",
        translation_key="co_alarm_status",
        device_class=SensorDeviceClass.ENUM,
        options=ALARM_STATUS_OPTIONS,
        value_fn=lambda shadow: shadow.co_alarm_status,
    ),
    PlaceAlarmSensorEntityDescription(
        key="heat_alarm_status",
        translation_key="heat_alarm_status",
        device_class=SensorDeviceClass.ENUM,
        options=ALARM_STATUS_OPTIONS,
        value_fn=lambda shadow: shadow.heat_alarm_status,
    ),
    PlaceAlarmSensorEntityDescription(
        key="smoke_alarm_status",
        translation_key="smoke_alarm_status",
        device_class=SensorDeviceClass.ENUM,
        options=ALARM_STATUS_OPTIONS,
        value_fn=lambda shadow: shadow.smoke_alarm_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Place alarm sensor entities."""
    coordinator = entry.runtime_data

    entities: list[PlaceAlarmSensorEntity] = [
        PlaceAlarmSensorEntity(coordinator, device, description)
        for device in coordinator.devices
        if device.thing_name
        for description in ALARM_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class PlaceAlarmSensorEntity(CoordinatorEntity[PlaceCoordinator], SensorEntity):
    """Sensor entity for a Place alarm status."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    entity_description: PlaceAlarmSensorEntityDescription

    def __init__(
        self,
        coordinator: PlaceCoordinator,
        device: DiscoverDevice,
        description: PlaceAlarmSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
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

    @property
    def native_value(self) -> str | None:
        """Return the current alarm status as a lowercase enum name."""
        shadow = (
            self.coordinator.data.get(self._thing_name)
            if self.coordinator.data
            else None
        )
        if shadow is None:
            return None
        return self.entity_description.value_fn(shadow).name.lower()

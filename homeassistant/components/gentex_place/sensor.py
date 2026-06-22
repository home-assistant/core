"""Sensor platform for the Place integration."""

from collections.abc import Callable
from dataclasses import dataclass

from place.models.discover_device import DiscoverDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AlarmStatus
from .coordinator import PlaceConfigEntry, PlaceCoordinator
from .models import PlaceDeviceShadow

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


class PlaceAlarmSensorEntity(SensorEntity):
    """Sensor entity for a Place alarm status."""

    _attr_has_entity_name = True

    entity_description: PlaceAlarmSensorEntityDescription

    def __init__(
        self,
        coordinator: PlaceCoordinator,
        device: DiscoverDevice,
        description: PlaceAlarmSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._thing_name: str = device.thing_name
        self._device_identifier: str = (
            device.location or device.device_name or device.device_id
        )
        self.entity_description = description
        self._attr_unique_id = f"{self._device_identifier}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={("gentex_place", self._device_identifier)},
            name=self._device_identifier,
            manufacturer="Gentex",
            model=getattr(device, "model_number", None),
            sw_version=getattr(device, "firmware_version", None),
        )

    @property
    def native_value(self) -> str | None:
        """Return the current alarm status as a lowercase enum name."""
        shadow = self.coordinator.shadows.get(self._thing_name)
        if shadow is None:
            return None
        return self.entity_description.value_fn(shadow).name.lower()

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

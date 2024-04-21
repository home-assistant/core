"""Interfaces with TotalConnect sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from total_connect_client.location import TotalConnectLocation
from total_connect_client.zone import TotalConnectZone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TotalConnectDataUpdateCoordinator
from .const import DOMAIN

LOW_BATTERY = "low_battery"
TAMPER = "tamper"
POWER = "power"
ZONE = "zone"

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TotalConnectZoneBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes TotalConnect binary sensor entity."""

    device_class_fn: Callable[[TotalConnectZone], BinarySensorDeviceClass] | None = None
    is_on_fn: Callable[[TotalConnectZone], bool]


def get_security_zone_device_class(zone: TotalConnectZone) -> BinarySensorDeviceClass:
    """Return the device class of a TotalConnect security zone."""
    if zone.is_type_fire():
        return BinarySensorDeviceClass.SMOKE
    if zone.is_type_carbon_monoxide():
        return BinarySensorDeviceClass.GAS
    if zone.is_type_motion():
        return BinarySensorDeviceClass.MOTION
    if zone.is_type_medical():
        return BinarySensorDeviceClass.SAFETY
    if zone.is_type_temperature():
        return BinarySensorDeviceClass.PROBLEM
    return BinarySensorDeviceClass.DOOR


SECURITY_BINARY_SENSOR = TotalConnectZoneBinarySensorEntityDescription(
    key=ZONE,
    name="",
    device_class_fn=get_security_zone_device_class,
    is_on_fn=lambda zone: zone.is_faulted() or zone.is_triggered(),
)

NO_BUTTON_BINARY_SENSORS: tuple[TotalConnectZoneBinarySensorEntityDescription, ...] = (
    TotalConnectZoneBinarySensorEntityDescription(
        key=LOW_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=" low battery",
        is_on_fn=lambda zone: zone.is_low_battery(),
    ),
    TotalConnectZoneBinarySensorEntityDescription(
        key=TAMPER,
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=f" {TAMPER}",
        is_on_fn=lambda zone: zone.is_tampered(),
    ),
)


@dataclass(frozen=True, kw_only=True)
class TotalConnectAlarmBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes TotalConnect binary sensor entity."""

    is_on_fn: Callable[[TotalConnectLocation], bool]


LOCATION_BINARY_SENSORS: tuple[TotalConnectAlarmBinarySensorEntityDescription, ...] = (
    TotalConnectAlarmBinarySensorEntityDescription(
        key=LOW_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=" low battery",
        is_on_fn=lambda location: location.is_low_battery(),
    ),
    TotalConnectAlarmBinarySensorEntityDescription(
        key=TAMPER,
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=f" {TAMPER}",
        is_on_fn=lambda location: location.is_cover_tampered(),
    ),
    TotalConnectAlarmBinarySensorEntityDescription(
        key=POWER,
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=f" {POWER}",
        is_on_fn=lambda location: location.is_ac_loss(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up TotalConnect device sensors based on a config entry."""
    sensors: list = []

    coordinator: TotalConnectDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    client_locations = coordinator.client.locations

    for location_id, location in client_locations.items():
        sensors.extend(
            TotalConnectAlarmBinarySensor(coordinator, description, location)
            for description in LOCATION_BINARY_SENSORS
        )

        for zone in location.zones.values():
            sensors.append(
                TotalConnectZoneBinarySensor(
                    coordinator, SECURITY_BINARY_SENSOR, location_id, zone
                )
            )

            if not zone.is_type_button():
                sensors.extend(
                    TotalConnectZoneBinarySensor(
                        coordinator,
                        description,
                        location_id,
                        zone,
                    )
                    for description in NO_BUTTON_BINARY_SENSORS
                )

    async_add_entities(sensors)


class TotalConnectZoneBinarySensor(
    CoordinatorEntity[TotalConnectDataUpdateCoordinator], BinarySensorEntity
):
    """Represent an TotalConnect zone."""

    entity_description: TotalConnectZoneBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        entity_description: TotalConnectZoneBinarySensorEntityDescription,
        location_id: str,
        zone: TotalConnectZone,
    ) -> None:
        """Initialize the TotalConnect status."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._location_id = location_id
        self._zone = zone
        self._attr_name = f"{zone.description}{entity_description.name}"
        self._attr_unique_id = f"{location_id}_{zone.zoneid}_{entity_description.key}"
        self._attr_is_on = None
        self._attr_extra_state_attributes = {
            "zone_id": zone.zoneid,
            "location_id": self._location_id,
            "partition": zone.partition,
        }
        identifier = zone.sensor_serial_number or f"zone_{zone.zoneid}"
        self._attr_device_info = DeviceInfo(
            name=zone.description,
            identifiers={(DOMAIN, identifier)},
            serial_number=zone.sensor_serial_number,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the entity."""
        return self.entity_description.is_on_fn(self._zone)

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this zone."""
        if self.entity_description.device_class_fn:
            return self.entity_description.device_class_fn(self._zone)
        return super().device_class


class TotalConnectAlarmBinarySensor(
    CoordinatorEntity[TotalConnectDataUpdateCoordinator], BinarySensorEntity
):
    """Represent a TotalConnect alarm device binary sensors."""

    entity_description: TotalConnectAlarmBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        entity_description: TotalConnectAlarmBinarySensorEntityDescription,
        location: TotalConnectLocation,
    ) -> None:
        """Initialize the TotalConnect alarm device binary sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._location = location
        self._attr_name = f"{location.location_name}{entity_description.name}"
        self._attr_unique_id = f"{location.location_id}_{entity_description.key}"
        self._attr_extra_state_attributes = {
            "location_id": location.location_id,
        }

    @property
    def is_on(self) -> bool:
        """Return the state of the entity."""
        return self.entity_description.is_on_fn(self._location)

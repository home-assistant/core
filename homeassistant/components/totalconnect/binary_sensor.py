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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TotalConnectConfigEntry, TotalConnectDataUpdateCoordinator
from .entity import TotalConnectLocationEntity, TotalConnectZoneEntity

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
    name=None,
    device_class_fn=get_security_zone_device_class,
    is_on_fn=lambda zone: zone.is_faulted() or zone.is_triggered(),
)

NO_BUTTON_BINARY_SENSORS: tuple[TotalConnectZoneBinarySensorEntityDescription, ...] = (
    TotalConnectZoneBinarySensorEntityDescription(
        key=LOW_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda zone: zone.is_low_battery(),
    ),
    TotalConnectZoneBinarySensorEntityDescription(
        key=TAMPER,
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
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
        is_on_fn=lambda location: location.is_low_battery(),
    ),
    TotalConnectAlarmBinarySensorEntityDescription(
        key=TAMPER,
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda location: location.is_cover_tampered(),
    ),
    TotalConnectAlarmBinarySensorEntityDescription(
        key=POWER,
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda location: location.is_ac_loss(),
    ),
    TotalConnectAlarmBinarySensorEntityDescription(
        key="smoke",
        device_class=BinarySensorDeviceClass.SMOKE,
        is_on_fn=lambda location: location.arming_state.is_triggered_fire(),
    ),
    TotalConnectAlarmBinarySensorEntityDescription(
        key="carbon_monoxide",
        device_class=BinarySensorDeviceClass.CO,
        is_on_fn=lambda location: location.arming_state.is_triggered_gas(),
    ),
    TotalConnectAlarmBinarySensorEntityDescription(
        key="police",
        translation_key="police",
        is_on_fn=lambda location: location.arming_state.is_triggered_police(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TotalConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TotalConnect device sensors based on a config entry."""
    sensors: list = []

    coordinator = entry.runtime_data

    client_locations = coordinator.client.locations

    for location_id, location in client_locations.items():
        sensors.extend(
            TotalConnectAlarmBinarySensor(coordinator, description, location)
            for description in LOCATION_BINARY_SENSORS
        )

        for zone in location.zones.values():
            sensors.append(
                TotalConnectZoneBinarySensor(
                    coordinator, SECURITY_BINARY_SENSOR, zone, location_id
                )
            )

            if not zone.is_type_button():
                sensors.extend(
                    TotalConnectZoneBinarySensor(
                        coordinator,
                        description,
                        zone,
                        location_id,
                    )
                    for description in NO_BUTTON_BINARY_SENSORS
                )

    async_add_entities(sensors)


class TotalConnectZoneBinarySensor(TotalConnectZoneEntity, BinarySensorEntity):
    """Represent a TotalConnect zone."""

    entity_description: TotalConnectZoneBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        entity_description: TotalConnectZoneBinarySensorEntityDescription,
        zone: TotalConnectZone,
        location_id: str,
    ) -> None:
        """Initialize the TotalConnect status."""
        super().__init__(coordinator, zone, location_id, entity_description.key)
        self.entity_description = entity_description
        self._attr_extra_state_attributes = {
            "zone_id": zone.zoneid,
            "location_id": location_id,
            "partition": zone.partition,
        }

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


class TotalConnectAlarmBinarySensor(TotalConnectLocationEntity, BinarySensorEntity):
    """Represent a TotalConnect alarm device binary sensors."""

    entity_description: TotalConnectAlarmBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        entity_description: TotalConnectAlarmBinarySensorEntityDescription,
        location: TotalConnectLocation,
    ) -> None:
        """Initialize the TotalConnect alarm device binary sensor."""
        super().__init__(coordinator, location)
        self.entity_description = entity_description
        self._attr_unique_id = f"{location.location_id}_{entity_description.key}"
        self._attr_extra_state_attributes = {
            "location_id": location.location_id,
        }

    @property
    def is_on(self) -> bool:
        """Return the state of the entity."""
        return self.entity_description.is_on_fn(self._location)

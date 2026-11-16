"""Support for iZone sensors."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from operator import attrgetter
from typing import override

from pizone import Controller, Power, PowerChannel, PowerDevice, PowerGroup, Zone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import IZoneConfigEntry, IZoneCoordinator
from .entity import IZoneCoordinatorEntity, zone_device_info

PARALLEL_UPDATES = 0

type IZoneSensorSource = (
    Controller | Zone | Power | PowerDevice | PowerChannel | PowerGroup
)


@dataclass(frozen=True, kw_only=True)
class IZoneSensorEntityDescription[SourceT: IZoneSensorSource](SensorEntityDescription):
    """Describes an iZone sensor; value_fn reads from a pizone source object."""

    value_fn: Callable[[SourceT], StateType]


CONTROLLER_SENSOR_DESCRIPTIONS: tuple[IZoneSensorEntityDescription[Controller], ...] = (
    IZoneSensorEntityDescription[Controller](
        key="supply_temperature",
        translation_key="supply_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("temp_supply"),
    ),
    IZoneSensorEntityDescription[Controller](
        key="return_temperature",
        translation_key="return_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=attrgetter("temp_return"),
    ),
)

DAMPER_POSITION_DESCRIPTION = IZoneSensorEntityDescription[Zone](
    key="damper_position",
    translation_key="damper_position",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=attrgetter("damper_position"),
)

RF_SIGNAL_PERCENT = {
    Zone.RfSignal.FULL: 100,
    Zone.RfSignal.HALF: 50,
    Zone.RfSignal.QUARTER: 25,
    Zone.RfSignal.NONE: 0,
}
BATTERY_LEVEL_PERCENT = {
    Zone.BatteryLevel.FULL: 100,
    Zone.BatteryLevel.HALF: 50,
    Zone.BatteryLevel.EMPTY: 0,
}

# Wired sensors misleadingly report RF signal and battery as 0 (full).
WIRELESS_SENSOR_TYPES = (Zone.SensorType.WIRELESS, Zone.SensorType.CSM)

WIRELESS_ZONE_SENSOR_DESCRIPTIONS: tuple[IZoneSensorEntityDescription[Zone], ...] = (
    IZoneSensorEntityDescription[Zone](
        key="rf_signal",
        translation_key="rf_signal",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda zone: (
            None if zone.rf_signal is None else RF_SIGNAL_PERCENT[zone.rf_signal]
        ),
    ),
    IZoneSensorEntityDescription[Zone](
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda zone: (
            None
            if zone.battery_level is None
            else BATTERY_LEVEL_PERCENT[zone.battery_level]
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IZoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up iZone sensor entities from the entry coordinator."""
    coordinator = entry.runtime_data
    controller = coordinator.controller
    # Bridges without damper position feedback report a constant 50.
    damper_position = replace(
        DAMPER_POSITION_DESCRIPTION,
        entity_registry_enabled_default=any(
            zone.damper_position not in (None, 50) for zone in controller.zones
        ),
    )
    async_add_entities(
        [
            *(
                IZoneSensor(
                    coordinator,
                    description,
                    controller,
                    unique_id=f"{controller.device_uid}_{description.key}",
                    device_info=DeviceInfo(
                        identifiers={(DOMAIN, controller.device_uid)},
                        manufacturer="IZone",
                        model=controller.sys_type,
                        name=f"iZone Controller {controller.device_uid}",
                    ),
                )
                for description in CONTROLLER_SENSOR_DESCRIPTIONS
            ),
            *(
                IZoneSensor(
                    coordinator,
                    damper_position,
                    zone,
                    unique_id=f"{controller.device_uid}_z{zone.index + 1}_damper_position",
                    device_info=zone_device_info(coordinator, zone),
                )
                for zone in controller.zones
                if zone.damper_position is not None
            ),
            *(
                IZoneSensor(
                    coordinator,
                    description,
                    zone,
                    unique_id=f"{controller.device_uid}_z{zone.index + 1}_{description.key}",
                    device_info=zone_device_info(coordinator, zone),
                )
                for zone in controller.zones
                if zone.sensor_type in WIRELESS_SENSOR_TYPES
                for description in WIRELESS_ZONE_SENSOR_DESCRIPTIONS
                if description.value_fn(zone) is not None
            ),
        ]
    )


class IZoneSensor[SourceT: IZoneSensorSource](IZoneCoordinatorEntity, SensorEntity):
    """Sensor backed by a pizone Controller, Zone, or Power* object."""

    _attr_has_entity_name = True
    entity_description: IZoneSensorEntityDescription[SourceT]

    def __init__(
        self,
        coordinator: IZoneCoordinator,
        description: IZoneSensorEntityDescription[SourceT],
        source: SourceT,
        *,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor for *source*."""
        super().__init__(coordinator)
        self.entity_description = description
        self._source = source
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value from the pizone source object."""
        return self.entity_description.value_fn(self._source)

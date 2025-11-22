"""Volvo binary sensors."""

from __future__ import annotations

from dataclasses import dataclass, field

from volvocarsapi.models import VolvoCarsApiBaseModel, VolvoCarsValue

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import API_NONE_VALUE
from .coordinator import VolvoConfigEntry
from .entity import VolvoEntity, VolvoEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VolvoBinarySensorDescription(
    BinarySensorEntityDescription, VolvoEntityDescription
):
    """Describes a Volvo binary sensor entity."""

    on_values: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class VolvoCarsDoorDescription(VolvoBinarySensorDescription):
    """Describes a Volvo door entity."""

    device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.DOOR
    on_values: tuple[str, ...] = field(default=("OPEN", "AJAR"), init=False)


@dataclass(frozen=True, kw_only=True)
class VolvoCarsTireDescription(VolvoBinarySensorDescription):
    """Describes a Volvo tire entity."""

    device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.PROBLEM
    on_values: tuple[str, ...] = field(
        default=("VERY_LOW_PRESSURE", "LOW_PRESSURE", "HIGH_PRESSURE"), init=False
    )


@dataclass(frozen=True, kw_only=True)
class VolvoCarsWindowDescription(VolvoBinarySensorDescription):
    """Describes a Volvo window entity."""

    device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.WINDOW
    on_values: tuple[str, ...] = field(default=("OPEN", "AJAR"), init=False)


_DESCRIPTIONS: tuple[VolvoBinarySensorDescription, ...] = (
    # brakes endpoint
    VolvoBinarySensorDescription(
        key="brake_fluid_level_warning",
        api_field="brakeFluidLevelWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("TOO_LOW",),
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="brake_light_center_warning",
        api_field="brakeLightCenterWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="brake_light_left_warning",
        api_field="brakeLightLeftWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="brake_light_right_warning",
        api_field="brakeLightRightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # engine endpoint
    VolvoBinarySensorDescription(
        key="coolant_level_warning",
        api_field="engineCoolantLevelWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("TOO_LOW",),
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="daytime_running_light_left_warning",
        api_field="daytimeRunningLightLeftWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="daytime_running_light_right_warning",
        api_field="daytimeRunningLightRightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # doors endpoint
    VolvoCarsDoorDescription(
        key="door_front_left",
        api_field="frontLeftDoor",
    ),
    # doors endpoint
    VolvoCarsDoorDescription(
        key="door_front_right",
        api_field="frontRightDoor",
    ),
    # doors endpoint
    VolvoCarsDoorDescription(
        key="door_rear_left",
        api_field="rearLeftDoor",
    ),
    # doors endpoint
    VolvoCarsDoorDescription(
        key="door_rear_right",
        api_field="rearRightDoor",
    ),
    # engine-status endpoint
    VolvoBinarySensorDescription(
        key="engine_status",
        api_field="engineStatus",
        device_class=BinarySensorDeviceClass.RUNNING,
        on_values=("RUNNING",),
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="fog_light_front_warning",
        api_field="fogLightFrontWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="fog_light_rear_warning",
        api_field="fogLightRearWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="hazard_lights_warning",
        api_field="hazardLightsWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="high_beam_left_warning",
        api_field="highBeamLeftWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="high_beam_right_warning",
        api_field="highBeamRightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # doors endpoint
    VolvoCarsDoorDescription(
        key="hood",
        api_field="hood",
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="low_beam_left_warning",
        api_field="lowBeamLeftWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="low_beam_right_warning",
        api_field="lowBeamRightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # engine endpoint
    VolvoBinarySensorDescription(
        key="oil_level_warning",
        api_field="oilLevelWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("SERVICE_REQUIRED", "TOO_LOW", "TOO_HIGH"),
    ),
    # position lights
    VolvoBinarySensorDescription(
        key="position_light_front_left_warning",
        api_field="positionLightFrontLeftWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # position lights
    VolvoBinarySensorDescription(
        key="position_light_front_right_warning",
        api_field="positionLightFrontRightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # position lights
    VolvoBinarySensorDescription(
        key="position_light_rear_left_warning",
        api_field="positionLightRearLeftWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # position lights
    VolvoBinarySensorDescription(
        key="position_light_rear_right_warning",
        api_field="positionLightRearRightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # registration plate light
    VolvoBinarySensorDescription(
        key="registration_plate_light_warning",
        api_field="registrationPlateLightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # reverse lights
    VolvoBinarySensorDescription(
        key="reverse_lights_warning",
        api_field="reverseLightsWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="side_mark_lights_warning",
        api_field="sideMarkLightsWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # windows endpoint
    VolvoCarsWindowDescription(
        key="sunroof",
        api_field="sunroof",
    ),
    # tyres endpoint
    VolvoCarsTireDescription(
        key="tire_front_left",
        api_field="frontLeft",
    ),
    # tyres endpoint
    VolvoCarsTireDescription(
        key="tire_front_right",
        api_field="frontRight",
    ),
    # tyres endpoint
    VolvoCarsTireDescription(
        key="tire_rear_left",
        api_field="rearLeft",
    ),
    # tyres endpoint
    VolvoCarsTireDescription(
        key="tire_rear_right",
        api_field="rearRight",
    ),
    # doors endpoint
    VolvoCarsDoorDescription(
        key="tailgate",
        api_field="tailgate",
    ),
    # doors endpoint
    VolvoCarsDoorDescription(
        key="tank_lid",
        api_field="tankLid",
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="turn_indication_front_left_warning",
        api_field="turnIndicationFrontLeftWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="turn_indication_front_right_warning",
        api_field="turnIndicationFrontRightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="turn_indication_rear_left_warning",
        api_field="turnIndicationRearLeftWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # warnings endpoint
    VolvoBinarySensorDescription(
        key="turn_indication_rear_right_warning",
        api_field="turnIndicationRearRightWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("FAILURE",),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # diagnostics endpoint
    VolvoBinarySensorDescription(
        key="washer_fluid_level_warning",
        api_field="washerFluidLevelWarning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        on_values=("TOO_LOW",),
    ),
    # windows endpoint
    VolvoCarsWindowDescription(
        key="window_front_left",
        api_field="frontLeftWindow",
    ),
    # windows endpoint
    VolvoCarsWindowDescription(
        key="window_front_right",
        api_field="frontRightWindow",
    ),
    # windows endpoint
    VolvoCarsWindowDescription(
        key="window_rear_left",
        api_field="rearLeftWindow",
    ),
    # windows endpoint
    VolvoCarsWindowDescription(
        key="window_rear_right",
        api_field="rearRightWindow",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinators = entry.runtime_data.interval_coordinators
    async_add_entities(
        VolvoBinarySensor(coordinator, description)
        for coordinator in coordinators
        for description in _DESCRIPTIONS
        if description.api_field in coordinator.data
    )


class VolvoBinarySensor(VolvoEntity, BinarySensorEntity):
    """Volvo binary sensor."""

    entity_description: VolvoBinarySensorDescription

    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        """Update the state of the entity."""
        if api_field is None:
            self._attr_is_on = None
            return

        assert isinstance(api_field, VolvoCarsValue)
        assert isinstance(api_field.value, str)

        value = api_field.value

        self._attr_is_on = (
            value in self.entity_description.on_values
            if value.upper() != API_NONE_VALUE
            else None
        )

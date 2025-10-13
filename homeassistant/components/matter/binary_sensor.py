"""Matter binary sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from chip.clusters import Objects as clusters
from chip.clusters.Objects import uint
from chip.clusters.Types import Nullable, NullValue
from matter_server.client.models import device_types

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LabelPlacement, MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter binary sensor from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.BINARY_SENSOR, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterBinarySensorEntityDescription(
    BinarySensorEntityDescription, MatterEntityDescription
):
    """Describe Matter binary sensor entities."""


class MatterBinarySensor(MatterEntity, BinarySensorEntity):
    """Representation of a Matter binary sensor."""

    entity_description: MatterBinarySensorEntityDescription

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value: bool | uint | int | Nullable | None
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value in (None, NullValue):
            value = None
        elif value_convert := self.entity_description.device_to_ha:
            value = value_convert(value)
        if TYPE_CHECKING:
            value = cast(bool | None, value)
        self._attr_is_on = value


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    # device specific: translate Hue motion to sensor to HA Motion sensor
    # instead of generic occupancy sensor
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="HueMotionSensor",
            device_class=BinarySensorDeviceClass.MOTION,
            device_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.OccupancySensing.Attributes.Occupancy,),
        vendor_id=(4107,),
        product_name=("Hue motion sensor",),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="OccupancySensor",
            device_class=BinarySensorDeviceClass.OCCUPANCY,
            # The first bit = if occupied
            device_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.OccupancySensing.Attributes.Occupancy,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="ThermostatOccupancySensor",
            device_class=BinarySensorDeviceClass.OCCUPANCY,
            # The first bit = if occupied
            device_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.Thermostat.Attributes.Occupancy,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="BatteryChargeLevel",
            device_class=BinarySensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_to_ha=lambda x: x
            != clusters.PowerSource.Enums.BatChargeLevelEnum.kOk,
            label_placement=LabelPlacement.IGNORE,  # do not use label for battery sensors
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.PowerSource.Attributes.BatChargeLevel,),
        # only add binary battery sensor if a regular percentage based is not available
        absent_attributes=(clusters.PowerSource.Attributes.BatPercentRemaining,),
    ),
    # BooleanState sensors (tied to device type)
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="ContactSensor",
            device_class=BinarySensorDeviceClass.DOOR,
            # value is inverted on matter to what we expect
            device_to_ha=lambda x: not x,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.BooleanState.Attributes.StateValue,),
        device_type=(device_types.ContactSensor,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="WaterLeakDetector",
            translation_key="water_leak",
            device_class=BinarySensorDeviceClass.MOISTURE,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.BooleanState.Attributes.StateValue,),
        device_type=(device_types.WaterLeakDetector,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="WaterFreezeDetector",
            translation_key="water_freeze",
            device_class=BinarySensorDeviceClass.COLD,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.BooleanState.Attributes.StateValue,),
        device_type=(device_types.WaterFreezeDetector,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="RainSensor",
            translation_key="rain",
            device_class=BinarySensorDeviceClass.MOISTURE,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.BooleanState.Attributes.StateValue,),
        device_type=(device_types.RainSensor,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="LockDoorStateSensor",
            device_class=BinarySensorDeviceClass.DOOR,
            device_to_ha={
                clusters.DoorLock.Enums.DoorStateEnum.kDoorOpen: True,
                clusters.DoorLock.Enums.DoorStateEnum.kDoorJammed: True,
                clusters.DoorLock.Enums.DoorStateEnum.kDoorForcedOpen: True,
                clusters.DoorLock.Enums.DoorStateEnum.kDoorClosed: False,
            }.get,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.DoorLock.Attributes.DoorState,),
        featuremap_contains=clusters.DoorLock.Bitmaps.Feature.kDoorPositionSensor,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="SmokeCoAlarmDeviceMutedSensor",
            device_to_ha=lambda x: (
                x == clusters.SmokeCoAlarm.Enums.MuteStateEnum.kMuted
            ),
            translation_key="muted",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.DeviceMuted,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="SmokeCoAlarmEndfOfServiceSensor",
            device_to_ha=lambda x: (
                x == clusters.SmokeCoAlarm.Enums.EndOfServiceEnum.kExpired
            ),
            translation_key="end_of_service",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.EndOfServiceAlert,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="SmokeCoAlarmBatteryAlertSensor",
            device_to_ha=lambda x: (
                x != clusters.SmokeCoAlarm.Enums.AlarmStateEnum.kNormal
            ),
            translation_key="battery_alert",
            device_class=BinarySensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.BatteryAlert,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="SmokeCoAlarmTestInProgressSensor",
            translation_key="test_in_progress",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.TestInProgress,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="SmokeCoAlarmHardwareFaultAlertSensor",
            translation_key="hardware_fault",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.HardwareFaultAlert,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="SmokeCoAlarmSmokeStateSensor",
            device_class=BinarySensorDeviceClass.SMOKE,
            device_to_ha=lambda x: (
                x != clusters.SmokeCoAlarm.Enums.AlarmStateEnum.kNormal
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.SmokeState,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="SmokeCoAlarmInterconnectSmokeAlarmSensor",
            device_class=BinarySensorDeviceClass.SMOKE,
            device_to_ha=lambda x: (
                x != clusters.SmokeCoAlarm.Enums.AlarmStateEnum.kNormal
            ),
            translation_key="interconnected_smoke_alarm",
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.InterconnectSmokeAlarm,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="SmokeCoAlarmInterconnectCOAlarmSensor",
            device_class=BinarySensorDeviceClass.CO,
            device_to_ha=lambda x: (
                x != clusters.SmokeCoAlarm.Enums.AlarmStateEnum.kNormal
            ),
            translation_key="interconnected_co_alarm",
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.InterconnectCOAlarm,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="EnergyEvseChargingStatusSensor",
            translation_key="evse_charging_status",
            device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
            device_to_ha={
                clusters.EnergyEvse.Enums.StateEnum.kNotPluggedIn: False,
                clusters.EnergyEvse.Enums.StateEnum.kPluggedInNoDemand: False,
                clusters.EnergyEvse.Enums.StateEnum.kPluggedInDemand: False,
                clusters.EnergyEvse.Enums.StateEnum.kPluggedInCharging: True,
                clusters.EnergyEvse.Enums.StateEnum.kPluggedInDischarging: False,
                clusters.EnergyEvse.Enums.StateEnum.kSessionEnding: False,
                clusters.EnergyEvse.Enums.StateEnum.kFault: False,
            }.get,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.EnergyEvse.Attributes.State,),
        allow_multi=True,  # also used for sensor entity
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="EnergyEvsePlugStateSensor",
            translation_key="evse_plug_state",
            device_class=BinarySensorDeviceClass.PLUG,
            device_to_ha={
                clusters.EnergyEvse.Enums.StateEnum.kNotPluggedIn: False,
                clusters.EnergyEvse.Enums.StateEnum.kPluggedInNoDemand: True,
                clusters.EnergyEvse.Enums.StateEnum.kPluggedInDemand: True,
                clusters.EnergyEvse.Enums.StateEnum.kPluggedInCharging: True,
                clusters.EnergyEvse.Enums.StateEnum.kPluggedInDischarging: True,
                clusters.EnergyEvse.Enums.StateEnum.kSessionEnding: False,
                clusters.EnergyEvse.Enums.StateEnum.kFault: False,
            }.get,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.EnergyEvse.Attributes.State,),
        allow_multi=True,  # also used for sensor entity
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="EnergyEvseSupplyStateSensor",
            translation_key="evse_supply_state",
            device_class=BinarySensorDeviceClass.RUNNING,
            device_to_ha={
                clusters.EnergyEvse.Enums.SupplyStateEnum.kDisabled: False,
                clusters.EnergyEvse.Enums.SupplyStateEnum.kChargingEnabled: True,
                clusters.EnergyEvse.Enums.SupplyStateEnum.kDischargingEnabled: False,
                clusters.EnergyEvse.Enums.SupplyStateEnum.kDisabledDiagnostics: False,
            }.get,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.EnergyEvse.Attributes.SupplyState,),
        allow_multi=True,  # also used for sensor entity
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="WaterHeaterManagementBoostStateSensor",
            translation_key="boost_state",
            device_to_ha=lambda x: (
                x == clusters.WaterHeaterManagement.Enums.BoostStateEnum.kActive
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.WaterHeaterManagement.Attributes.BoostState,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="PumpFault",
            translation_key="pump_fault",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            # DeviceFault or SupplyFault bit enabled
            device_to_ha={
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kDeviceFault: True,
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kSupplyFault: True,
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kSpeedLow: False,
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kSpeedHigh: False,
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kLocalOverride: False,
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kRunning: False,
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kRemotePressure: False,
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kRemoteFlow: False,
                clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kRemoteTemperature: False,
            }.get,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(
            clusters.PumpConfigurationAndControl.Attributes.PumpStatus,
        ),
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="PumpStatusRunning",
            translation_key="pump_running",
            device_class=BinarySensorDeviceClass.RUNNING,
            device_to_ha=lambda x: (
                x
                == clusters.PumpConfigurationAndControl.Bitmaps.PumpStatusBitmap.kRunning
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(
            clusters.PumpConfigurationAndControl.Attributes.PumpStatus,
        ),
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="DishwasherAlarmInflowError",
            translation_key="dishwasher_alarm_inflow",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_to_ha=lambda x: (
                x == clusters.DishwasherAlarm.Bitmaps.AlarmBitmap.kInflowError
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.DishwasherAlarm.Attributes.State,),
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="DishwasherAlarmDoorError",
            translation_key="alarm_door",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_to_ha=lambda x: (
                x == clusters.DishwasherAlarm.Bitmaps.AlarmBitmap.kDoorError
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.DishwasherAlarm.Attributes.State,),
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="ValveConfigurationAndControlValveFault_GeneralFault",
            translation_key="valve_fault_general_fault",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_to_ha=lambda x: (
                x
                == clusters.ValveConfigurationAndControl.Bitmaps.ValveFaultBitmap.kGeneralFault
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(
            clusters.ValveConfigurationAndControl.Attributes.ValveFault,
        ),
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="ValveConfigurationAndControlValveFault_Blocked",
            translation_key="valve_fault_blocked",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_to_ha=lambda x: (
                x
                == clusters.ValveConfigurationAndControl.Bitmaps.ValveFaultBitmap.kBlocked
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(
            clusters.ValveConfigurationAndControl.Attributes.ValveFault,
        ),
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="ValveConfigurationAndControlValveFault_Leaking",
            translation_key="valve_fault_leaking",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_to_ha=lambda x: (
                x
                == clusters.ValveConfigurationAndControl.Bitmaps.ValveFaultBitmap.kLeaking
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(
            clusters.ValveConfigurationAndControl.Attributes.ValveFault,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="RefrigeratorAlarmDoorOpen",
            translation_key="alarm_door",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_to_ha=lambda x: (
                x == clusters.RefrigeratorAlarm.Bitmaps.AlarmBitmap.kDoorOpen
            ),
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.RefrigeratorAlarm.Attributes.State,),
        allow_multi=True,
    ),
]

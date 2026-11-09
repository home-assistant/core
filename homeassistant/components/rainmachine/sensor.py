"""Support for sensor data from RainMachine."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp, utcnow

from . import RainMachineConfigEntry, RainMachineData
from .const import (
    CONF_USE_APP_RUN_TIMES,
    DATA_PROGRAMS,
    DATA_PROVISION_SETTINGS,
    DATA_ZONES,
)
from .entity import RainMachineEntity, RainMachineEntityDescription
from .util import RUN_STATE_MAP, RunStates, key_exists
from .zone import (
    SLOPE_TYPE_MAP,
    SOIL_TYPE_MAP,
    SPRINKLER_TYPE_MAP,
    SUN_EXPOSURE_MAP,
    VEGETATION_MAP,
)

DEFAULT_ZONE_COMPLETION_TIME_WOBBLE_TOLERANCE = timedelta(seconds=5)

TYPE_FLOW_SENSOR_CLICK_M3 = "flow_sensor_clicks_cubic_meter"
TYPE_FLOW_SENSOR_CONSUMED_LITERS = "flow_sensor_consumed_liters"
TYPE_FLOW_SENSOR_LEAK_CLICKS = "flow_sensor_leak_clicks"
TYPE_FLOW_SENSOR_LEAK_VOLUME = "flow_sensor_leak_volume"
TYPE_FLOW_SENSOR_START_INDEX = "flow_sensor_start_index"
TYPE_FLOW_SENSOR_WATERING_CLICKS = "flow_sensor_watering_clicks"
TYPE_LAST_LEAK_DETECTED = "last_leak_detected"
TYPE_PROGRAM_RUN_COMPLETION_TIME = "program_run_completion_time"
TYPE_RAIN_SENSOR_RAIN_START = "rain_sensor_rain_start"
TYPE_ZONE_RUN_COMPLETION_TIME = "zone_run_completion_time"


@dataclass(frozen=True, kw_only=True)
class RainMachineSensorDataDescription(
    SensorEntityDescription, RainMachineEntityDescription
):
    """Describe a RainMachine sensor."""

    data_key: str


@dataclass(frozen=True, kw_only=True)
class RainMachineSensorCompletionTimerDescription(
    SensorEntityDescription, RainMachineEntityDescription
):
    """Describe a RainMachine completion timer sensor."""

    uid: int


@dataclass(frozen=True, kw_only=True)
class RainMachineZoneWaterSenseSensorDescription(
    SensorEntityDescription, RainMachineEntityDescription
):
    """Describe a zone water-sense measurement."""

    uid: int
    data_key: str


@dataclass(frozen=True, kw_only=True)
class RainMachineZoneAttributeSensorDescription(
    SensorEntityDescription, RainMachineEntityDescription
):
    """Describe a zone attribute as a standalone sensor."""

    uid: int
    data_key: str
    value_map: Mapping[int, str] | None = None


ZONE_ATTRIBUTE_MEASUREMENTS: tuple[
    tuple[str, str, str, Mapping[int, str] | None], ...
] = (
    ("id", "ID", "uid", None),
    ("current_cycle", "Current cycle", "cycle", None),
    ("number_of_cycles", "Number of cycles", "noOfCycles", None),
    ("slope", "Slope", "slope", SLOPE_TYPE_MAP),
    ("soil_type", "Soil type", "soil", SOIL_TYPE_MAP),
    ("sprinkler_head_type", "Sprinkler head type", "group_id", SPRINKLER_TYPE_MAP),
    ("status", "Status", "state", RUN_STATE_MAP),
    ("sun_exposure", "Sun exposure", "sun", SUN_EXPOSURE_MAP),
    ("vegetation_type", "Vegetation type", "type", VEGETATION_MAP),
)


@dataclass(frozen=True, kw_only=True)
class RainMachineZoneAppRunTimeSensorDescription(
    SensorEntityDescription, RainMachineEntityDescription
):
    """Describe a zone app-configured run time."""

    uid: int


ZONE_WATER_SENSE_MEASUREMENTS = (
    ("area", "Area", "area"),
    ("field_capacity", "Field capacity", "fieldCapacity"),
    ("precipitation_rate", "Precipitation rate", "precipitationRate"),
)


SENSOR_DESCRIPTIONS = (
    RainMachineSensorDataDescription(
        key=TYPE_FLOW_SENSOR_CLICK_M3,
        translation_key=TYPE_FLOW_SENSOR_CLICK_M3,
        native_unit_of_measurement=f"clicks/{UnitOfVolume.CUBIC_METERS}",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorClicksPerCubicMeter",
    ),
    RainMachineSensorDataDescription(
        key=TYPE_FLOW_SENSOR_CONSUMED_LITERS,
        translation_key=TYPE_FLOW_SENSOR_CONSUMED_LITERS,
        device_class=SensorDeviceClass.WATER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorWateringClicks",
    ),
    RainMachineSensorDataDescription(
        key=TYPE_FLOW_SENSOR_LEAK_CLICKS,
        translation_key=TYPE_FLOW_SENSOR_LEAK_CLICKS,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="clicks",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorLeakClicks",
    ),
    RainMachineSensorDataDescription(
        key=TYPE_FLOW_SENSOR_LEAK_VOLUME,
        translation_key=TYPE_FLOW_SENSOR_LEAK_VOLUME,
        device_class=SensorDeviceClass.WATER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorLeakClicks",
    ),
    RainMachineSensorDataDescription(
        key=TYPE_FLOW_SENSOR_START_INDEX,
        translation_key=TYPE_FLOW_SENSOR_START_INDEX,
        icon="mdi:water-pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="index",
        entity_registry_enabled_default=False,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorStartIndex",
    ),
    RainMachineSensorDataDescription(
        key=TYPE_FLOW_SENSOR_WATERING_CLICKS,
        translation_key=TYPE_FLOW_SENSOR_WATERING_CLICKS,
        icon="mdi:water-pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="clicks",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorWateringClicks",
    ),
    RainMachineSensorDataDescription(
        key=TYPE_LAST_LEAK_DETECTED,
        translation_key=TYPE_LAST_LEAK_DETECTED,
        icon="mdi:pipe-leak",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="lastLeakDetected",
    ),
    RainMachineSensorDataDescription(
        key=TYPE_RAIN_SENSOR_RAIN_START,
        translation_key=TYPE_RAIN_SENSOR_RAIN_START,
        icon="mdi:weather-pouring",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="rainSensorRainStart",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainMachineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RainMachine sensors based on a config entry."""
    data = entry.runtime_data

    api_category_sensor_map = {
        DATA_PROVISION_SETTINGS: ProvisionSettingsSensor,
    }

    sensors: list[
        ProvisionSettingsSensor
        | TimeRemainingSensor
        | ZoneWaterSenseSensor
        | ZoneAttributeSensor
        | ZoneAppRunTimeSensor
    ] = [
        api_category_sensor_map[description.api_category](entry, data, description)
        for description in SENSOR_DESCRIPTIONS
        if (
            (coordinator := data.coordinators[description.api_category]) is not None
            and coordinator.data
            and key_exists(coordinator.data, description.data_key)
        )
    ]

    program_coordinator = data.coordinators[DATA_PROGRAMS]
    zone_coordinator = data.coordinators[DATA_ZONES]

    for uid, program in program_coordinator.data.items():
        sensors.append(
            ProgramTimeRemainingSensor(
                entry,
                data,
                RainMachineSensorCompletionTimerDescription(
                    key=f"{TYPE_PROGRAM_RUN_COMPLETION_TIME}_{uid}",
                    name=f"{program['name']} Run Completion Time",
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    api_category=DATA_PROGRAMS,
                    uid=uid,
                ),
            )
        )

    for uid, zone in zone_coordinator.data.items():
        sensors.append(
            ZoneTimeRemainingSensor(
                entry,
                data,
                RainMachineSensorCompletionTimerDescription(
                    key=f"{TYPE_ZONE_RUN_COMPLETION_TIME}_{uid}",
                    name=f"{zone['name']} Run Completion Time",
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    api_category=DATA_ZONES,
                    uid=uid,
                ),
            )
        )

    for uid, zone in zone_coordinator.data.items():
        water_sense = zone.get("waterSense") or {}
        for key, name, data_key in ZONE_WATER_SENSE_MEASUREMENTS:
            if data_key not in water_sense:
                continue
            sensors.append(
                ZoneWaterSenseSensor(
                    entry,
                    data,
                    RainMachineZoneWaterSenseSensorDescription(
                        key=f"zone_{uid}_{key}",
                        name=f"{zone['name']} {name}",
                        api_category=DATA_ZONES,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        state_class=SensorStateClass.MEASUREMENT,
                        uid=uid,
                        data_key=data_key,
                    ),
                )
            )

    for uid, zone in zone_coordinator.data.items():
        for key, name, data_key, value_map in ZONE_ATTRIBUTE_MEASUREMENTS:
            if data_key not in zone:
                continue
            sensors.append(
                ZoneAttributeSensor(
                    entry,
                    data,
                    RainMachineZoneAttributeSensorDescription(
                        key=f"zone_{uid}_{key}",
                        name=f"{zone['name']} {name}",
                        api_category=DATA_ZONES,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        state_class=(
                            SensorStateClass.MEASUREMENT
                            if key in {"current_cycle", "number_of_cycles"}
                            else None
                        ),
                        uid=uid,
                        data_key=data_key,
                        value_map=value_map,
                    ),
                )
            )

    if entry.options[CONF_USE_APP_RUN_TIMES]:
        zone_durations = (
            data.coordinators[DATA_PROVISION_SETTINGS]
            .data.get("system", {})
            .get("zoneDuration")
        )
        if zone_durations:
            for uid, zone in zone_coordinator.data.items():
                sensors.append(
                    ZoneAppRunTimeSensor(
                        entry,
                        data,
                        RainMachineZoneAppRunTimeSensorDescription(
                            key=f"zone_{uid}_zone_run_time_from_app",
                            name=f"{zone['name']} Run time from app",
                            api_category=DATA_PROVISION_SETTINGS,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            entity_registry_enabled_default=False,
                            device_class=SensorDeviceClass.DURATION,
                            native_unit_of_measurement=UnitOfTime.SECONDS,
                            state_class=SensorStateClass.MEASUREMENT,
                            uid=uid,
                        ),
                    )
                )

    async_add_entities(sensors)


class TimeRemainingSensor(RainMachineEntity, RestoreSensor):
    """Define a sensor that shows the amount of time remaining for an activity."""

    entity_description: RainMachineSensorCompletionTimerDescription

    def __init__(
        self,
        entry: RainMachineConfigEntry,
        data: RainMachineData,
        description: RainMachineSensorCompletionTimerDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, data, description)

        self._current_run_state: RunStates | None = None
        self._previous_run_state: RunStates | None = None

    @property
    def activity_data(self) -> dict[str, Any]:
        """Return the core data for this entity."""
        return cast(dict[str, Any], self.coordinator.data[self.entity_description.uid])

    @property
    def status_key(self) -> str:
        """Return the data key that contains the activity status."""
        return "state"

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        if restored_data := await self.async_get_last_sensor_data():
            self._attr_native_value = restored_data.native_value
        await super().async_added_to_hass()

    def calculate_seconds_remaining(self) -> int:
        """Calculate the number of seconds remaining."""
        raise NotImplementedError

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the state."""
        self._previous_run_state = self._current_run_state
        self._current_run_state = RUN_STATE_MAP.get(self.activity_data[self.status_key])

        now = utcnow()

        if (
            self._current_run_state == RunStates.NOT_RUNNING
            and self._previous_run_state in (RunStates.QUEUED, RunStates.RUNNING)
        ):
            # If the activity goes from queued/running to not running, update the
            # state to be right now (i.e., the time the zone stopped running):
            self._attr_native_value = now
        elif self._current_run_state == RunStates.RUNNING:
            seconds_remaining = self.calculate_seconds_remaining()
            new_timestamp = now + timedelta(seconds=seconds_remaining)

            if (
                isinstance(self._attr_native_value, datetime)
                and new_timestamp - self._attr_native_value
                < DEFAULT_ZONE_COMPLETION_TIME_WOBBLE_TOLERANCE
            ):
                # If the deviation between the previous and new timestamps is less
                # than a "wobble tolerance," don't spam the state machine:
                return

            self._attr_native_value = new_timestamp


class ProgramTimeRemainingSensor(TimeRemainingSensor):
    """Define a sensor that shows the amount of time remaining for a program."""

    @property
    @override
    def status_key(self) -> str:
        """Return the data key that contains the activity status."""
        return "status"

    @override
    def calculate_seconds_remaining(self) -> int:
        """Calculate the number of seconds remaining."""
        return sum(
            self._data.coordinators[DATA_ZONES].data[zone["id"]]["remaining"]
            for zone in [z for z in self.activity_data["wateringTimes"] if z["active"]]
        )


class ProvisionSettingsSensor(RainMachineEntity, SensorEntity):
    """Define a sensor that handles provisioning data."""

    entity_description: RainMachineSensorDataDescription

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the state."""
        system = self.coordinator.data.get("system", {})
        new_value = system.get(self.entity_description.data_key)

        # Calculate volumetric sensors
        if (
            self.entity_description.key
            in {
                TYPE_FLOW_SENSOR_CONSUMED_LITERS,
                TYPE_FLOW_SENSOR_LEAK_VOLUME,
            }
            and new_value
        ):
            if clicks_per_m3 := system.get("flowSensorClicksPerCubicMeter"):
                self._attr_native_value = round((new_value * 1000) / clicks_per_m3, 1)
                return

        # Convert timestamp sensors to datetime
        if self.entity_description.key in {
            TYPE_LAST_LEAK_DETECTED,
            TYPE_RAIN_SENSOR_RAIN_START,
        }:
            # Timestamp may return 0 instead of null, explicitly set to None
            if new_value:
                self._attr_native_value = utc_from_timestamp(new_value)
            else:
                self._attr_native_value = None
            return

        # Return all other sensor values or None
        self._attr_native_value = new_value


class ZoneTimeRemainingSensor(TimeRemainingSensor):
    """Define a sensor that shows the amount of time remaining for a zone."""

    @override
    def calculate_seconds_remaining(self) -> int:
        """Calculate the number of seconds remaining."""
        return cast(
            int, self.coordinator.data[self.entity_description.uid]["remaining"]
        )


class ZoneWaterSenseSensor(RainMachineEntity, SensorEntity):
    """Represent a RainMachine zone water-sense measurement."""

    entity_description: RainMachineZoneWaterSenseSensorDescription

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the sensor from its zone coordinator."""
        water_sense = (
            self.coordinator.data[self.entity_description.uid].get("waterSense") or {}
        )
        value = water_sense.get(self.entity_description.data_key)
        self._attr_native_value = round(value, 2) if value is not None else None


class ZoneAttributeSensor(RainMachineEntity, SensorEntity):
    """Represent an existing RainMachine zone attribute as a sensor."""

    entity_description: RainMachineZoneAttributeSensorDescription

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Read the zone attribute from the coordinator."""
        value = self.coordinator.data[self.entity_description.uid].get(
            self.entity_description.data_key
        )
        if value is not None and self.entity_description.value_map is not None:
            value = self.entity_description.value_map.get(value, "Other")
        self._attr_native_value = value


class ZoneAppRunTimeSensor(RainMachineEntity, SensorEntity):
    """Represent the per-zone duration from RainMachine provisioning settings."""

    entity_description: RainMachineZoneAppRunTimeSensorDescription

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Read the app-configured duration for this zone."""
        zone_durations = self.coordinator.data.get("system", {}).get("zoneDuration")
        if not zone_durations:
            self._attr_native_value = None
            return

        zone_ids = list(self._data.coordinators[DATA_ZONES].data)
        try:
            zone_index = zone_ids.index(self.entity_description.uid)
        except ValueError:
            self._attr_native_value = None
            return
        self._attr_native_value = (
            zone_durations[zone_index] if zone_index < len(zone_durations) else None
        )

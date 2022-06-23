"""This platform provides support for sensor data from RainMachine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from regenmaschine.controller import Controller

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, VOLUME_CUBIC_METERS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from . import RainMachineEntity
from .const import (
    DATA_CONTROLLER,
    DATA_COORDINATOR,
    DATA_PROGRAMS,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_UNIVERSAL,
    DATA_ZONES,
    DOMAIN,
    RUN_STATE_MAP,
    RunStates,
)
from .model import (
    RainMachineDescriptionMixinApiCategory,
    RainMachineDescriptionMixinUid,
)
from .util import key_exists

DEFAULT_ZONE_COMPLETION_TIME_WOBBLE_TOLERANCE = timedelta(seconds=5)

TYPE_FLOW_SENSOR_CLICK_M3 = "flow_sensor_clicks_cubic_meter"
TYPE_FLOW_SENSOR_CONSUMED_LITERS = "flow_sensor_consumed_liters"
TYPE_FLOW_SENSOR_START_INDEX = "flow_sensor_start_index"
TYPE_FLOW_SENSOR_WATERING_CLICKS = "flow_sensor_watering_clicks"
TYPE_FREEZE_TEMP = "freeze_protect_temp"
TYPE_PROGRAM_RUN_COMPLETION_TIME = "program_run_completion_time"
TYPE_ZONE_RUN_COMPLETION_TIME = "zone_run_completion_time"


@dataclass
class RainMachineSensorDescriptionApiCategory(
    SensorEntityDescription, RainMachineDescriptionMixinApiCategory
):
    """Describe a RainMachine sensor."""


@dataclass
class RainMachineSensorDescriptionUid(
    SensorEntityDescription, RainMachineDescriptionMixinUid
):
    """Describe a RainMachine sensor."""


SENSOR_DESCRIPTIONS = (
    RainMachineSensorDescriptionApiCategory(
        key=TYPE_FLOW_SENSOR_CLICK_M3,
        name="Flow Sensor Clicks per Cubic Meter",
        icon="mdi:water-pump",
        native_unit_of_measurement=f"clicks/{VOLUME_CUBIC_METERS}",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorClicksPerCubicMeter",
    ),
    RainMachineSensorDescriptionApiCategory(
        key=TYPE_FLOW_SENSOR_CONSUMED_LITERS,
        name="Flow Sensor Consumed Liters",
        icon="mdi:water-pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="liter",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorWateringClicks",
    ),
    RainMachineSensorDescriptionApiCategory(
        key=TYPE_FLOW_SENSOR_START_INDEX,
        name="Flow Sensor Start Index",
        icon="mdi:water-pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="index",
        entity_registry_enabled_default=False,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorStartIndex",
    ),
    RainMachineSensorDescriptionApiCategory(
        key=TYPE_FLOW_SENSOR_WATERING_CLICKS,
        name="Flow Sensor Clicks",
        icon="mdi:water-pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="clicks",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        api_category=DATA_PROVISION_SETTINGS,
        data_key="flowSensorWateringClicks",
    ),
    RainMachineSensorDescriptionApiCategory(
        key=TYPE_FREEZE_TEMP,
        name="Freeze Protect Temperature",
        icon="mdi:thermometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        api_category=DATA_RESTRICTIONS_UNIVERSAL,
        data_key="freezeProtectTemp",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up RainMachine sensors based on a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id][DATA_CONTROLLER]
    coordinators = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    api_category_sensor_map = {
        DATA_PROVISION_SETTINGS: ProvisionSettingsSensor,
        DATA_RESTRICTIONS_UNIVERSAL: UniversalRestrictionsSensor,
    }

    sensors = [
        api_category_sensor_map[description.api_category](
            entry, coordinator, controller, description
        )
        for description in SENSOR_DESCRIPTIONS
        if (
            (coordinator := coordinators[description.api_category]) is not None
            and coordinator.data
            and key_exists(coordinator.data, description.data_key)
        )
    ]

    program_coordinator = coordinators[DATA_PROGRAMS]
    zone_coordinator = coordinators[DATA_ZONES]

    for uid, program in program_coordinator.data.items():
        sensors.append(
            ProgramTimeRemainingSensor(
                entry,
                program_coordinator,
                zone_coordinator,
                controller,
                RainMachineSensorDescriptionUid(
                    key=f"{TYPE_PROGRAM_RUN_COMPLETION_TIME}_{uid}",
                    name=f"{program['name']} Run Completion Time",
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    uid=uid,
                ),
            )
        )

    for uid, zone in zone_coordinator.data.items():
        sensors.append(
            ZoneTimeRemainingSensor(
                entry,
                zone_coordinator,
                controller,
                RainMachineSensorDescriptionUid(
                    key=f"{TYPE_ZONE_RUN_COMPLETION_TIME}_{uid}",
                    name=f"{zone['name']} Run Completion Time",
                    device_class=SensorDeviceClass.TIMESTAMP,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    uid=uid,
                ),
            )
        )

    async_add_entities(sensors)


class TimeRemainingSensor(RainMachineEntity, SensorEntity):
    """Define a sensor that shows the amount of time remaining for an activity."""

    entity_description: RainMachineSensorDescriptionUid

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        controller: Controller,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinator, controller, description)

        self._running_or_queued: bool = False

    @property
    def status_key(self) -> str:
        """Return the data key that contains the activity status."""
        return "state"

    def calculate_seconds_remaining(self) -> int:
        """Calculate the number of seconds remaining."""
        raise NotImplementedError

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        data = self.coordinator.data[self.entity_description.uid]
        now = utcnow()

        if RUN_STATE_MAP.get(data[self.status_key]) == RunStates.NOT_RUNNING:
            if self._running_or_queued:
                # If we go from running to not running, update the state to be right
                # now (i.e., the time the zone stopped running):
                self._attr_native_value = now
                self._running_or_queued = False
            return

        self._running_or_queued = True
        if (seconds_remaining := self.calculate_seconds_remaining()) == 0:
            # The RainMachine API can take a moment to calculate zone runtimes when
            # starting a program (resulting in a 0-second duration). This is a
            # nonsensical value, so if it occurs, return immediately and pick things up
            # the next time the API polls:
            return

        new_timestamp = utcnow() + timedelta(seconds=seconds_remaining)

        if self._attr_native_value:
            assert isinstance(self._attr_native_value, datetime)
            if (
                new_timestamp - self._attr_native_value
            ) < DEFAULT_ZONE_COMPLETION_TIME_WOBBLE_TOLERANCE:
                # If the deviation between the previous and new timestamps is less than
                # a "wobble tolerance," don't spam the state machine:
                return

        self._attr_native_value = new_timestamp


class ProgramTimeRemainingSensor(TimeRemainingSensor):
    """Define a sensor that shows the amount of time remaining for a program."""

    def __init__(
        self,
        entry: ConfigEntry,
        program_coordinator: DataUpdateCoordinator,
        zone_coordinator: DataUpdateCoordinator,
        controller: Controller,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, program_coordinator, controller, description)

        self._zone_coordinator = zone_coordinator

    @property
    def status_key(self) -> str:
        """Return the data key that contains the activity status."""
        return "status"

    def calculate_seconds_remaining(self) -> int:
        """Calculate the number of seconds remaining."""
        program_data = self.coordinator.data[self.entity_description.uid]
        duration = 0

        for zone in program_data["wateringTimes"]:
            if not zone["active"]:
                continue

            # If the user has configured a manual delay between zones, add it to the
            # total duration:
            if program_data["delay_on"]:
                duration += program_data["delay"]

            duration += self._zone_coordinator.data[zone["id"]]["remaining"]

        return duration


class ProvisionSettingsSensor(RainMachineEntity, SensorEntity):
    """Define a sensor that handles provisioning data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self.entity_description.key == TYPE_FLOW_SENSOR_CLICK_M3:
            self._attr_native_value = self.coordinator.data["system"].get(
                "flowSensorClicksPerCubicMeter"
            )
        elif self.entity_description.key == TYPE_FLOW_SENSOR_CONSUMED_LITERS:
            clicks = self.coordinator.data["system"].get("flowSensorWateringClicks")
            clicks_per_m3 = self.coordinator.data["system"].get(
                "flowSensorClicksPerCubicMeter"
            )

            if clicks and clicks_per_m3:
                self._attr_native_value = (clicks * 1000) / clicks_per_m3
            else:
                self._attr_native_value = None
        elif self.entity_description.key == TYPE_FLOW_SENSOR_START_INDEX:
            self._attr_native_value = self.coordinator.data["system"].get(
                "flowSensorStartIndex"
            )
        elif self.entity_description.key == TYPE_FLOW_SENSOR_WATERING_CLICKS:
            self._attr_native_value = self.coordinator.data["system"].get(
                "flowSensorWateringClicks"
            )


class UniversalRestrictionsSensor(RainMachineEntity, SensorEntity):
    """Define a sensor that handles universal restrictions data."""

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
        if self.entity_description.key == TYPE_FREEZE_TEMP:
            self._attr_native_value = self.coordinator.data.get("freezeProtectTemp")


class ZoneTimeRemainingSensor(TimeRemainingSensor):
    """Define a sensor that shows the amount of time remaining for a zone."""

    def calculate_seconds_remaining(self) -> int:
        """Calculate the number of seconds remaining."""
        return cast(
            int, self.coordinator.data[self.entity_description.uid]["remaining"]
        )

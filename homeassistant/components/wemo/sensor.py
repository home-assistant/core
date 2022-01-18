"""Support for power sensors in WeMo Insight devices and for diagnostics."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from pywemo.util import ExtMetaInfo, signal_strength_to_dbm

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoEntity
from .wemo_device import (
    SLOW_UPDATE_INTERVAL,
    ActionCoordinator,
    ActionDescription,
    DeviceCoordinator,
    StateCoordinator,
    async_get_action_coordinator,
)


def _convert_uptime_to_timestamp(
    sensor: AttributeSensor, ext_meta_info: StateType
) -> datetime | None:
    """Convert a WeMo uptime into an ISO8601 boot timestamp."""
    uptime = ExtMetaInfo.from_ext_meta_info(cast(str, ext_meta_info)).uptime
    timestamp = dt.utcnow() - uptime

    # Avoid small deviations caused by network latency.
    if (previous := sensor.conversion_state.previous_boot_datetime) is not None:
        assert sensor.coordinator.update_interval is not None
        if timestamp - previous < sensor.coordinator.update_interval:
            timestamp = previous

    sensor.conversion_state.previous_boot_datetime = timestamp
    return timestamp


@dataclass
class AttributeSensorDescription(SensorEntityDescription):
    """SensorEntityDescription for WeMo AttributeSensor entities."""

    state_conversion: Callable[
        [AttributeSensor, StateType], StateType | datetime
    ] | None = None
    unique_id_suffix: str | None = None


@dataclass
class ActionSensorDescription(AttributeSensorDescription, ActionDescription):
    """SensorEntityDescription for WeMo ActionSensor entities."""


ATTRIBUTE_SENSORS = (
    AttributeSensorDescription(
        name="Current Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
        key="current_power_watts",
        unique_id_suffix="currentpower",
        state_conversion=lambda _, state: round(cast(float, state), 2),
    ),
    AttributeSensorDescription(
        name="Today Energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        key="today_kwh",
        unique_id_suffix="todaymw",
        state_conversion=lambda _, state: round(cast(float, state), 2),
    ),
    AttributeSensorDescription(
        name="IP Address",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:ip",
        key="host",
    ),
    AttributeSensorDescription(
        name="UPnP Port",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:connection",
        key="port",
    ),
)

ACTION_SENSORS = [
    ActionSensorDescription(
        name="WiFi Signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        wemo_service="basicevent",
        wemo_action="GetSignalStrength",
        key="SignalStrength",
        update_interval=SLOW_UPDATE_INTERVAL,
        state_conversion=lambda _, state: signal_strength_to_dbm(cast(str, state)),
    ),
    ActionSensorDescription(
        name="Boot Time",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-outline",
        wemo_service="metainfo",
        wemo_action="GetExtMetaInfo",
        key="ExtMetaInfo",
        update_interval=SLOW_UPDATE_INTERVAL,
        state_conversion=_convert_uptime_to_timestamp,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeMo sensors."""

    async def _discovered_wemo(coordinator: StateCoordinator) -> None:
        """Handle a discovered Wemo device."""
        sensors: list[SensorEntity] = []

        # Add action sensors.
        for description in ACTION_SENSORS:
            if description.upnp_action(coordinator.wemo) is None:
                continue
            action_coordinator = await async_get_action_coordinator(
                coordinator, description
            )
            sensors.append(ActionSensor(action_coordinator, description))

        # Add attribute sensors.
        sensors.extend(
            AttributeSensor(coordinator, description)
            for description in ATTRIBUTE_SENSORS
            if hasattr(coordinator.wemo, description.key)
        )

        async_add_entities(sensors)

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.sensor", _discovered_wemo)

    await asyncio.gather(
        *(
            _discovered_wemo(coordinator)
            for coordinator in hass.data[WEMO_DOMAIN]["pending"].pop("sensor")
        )
    )


@dataclass
class ConversionState:
    """Extra state variables required by some sensors."""

    previous_boot_datetime: datetime | None = None


class AttributeSensor(WemoEntity, SensorEntity):
    """Sensor that reads attributes of a wemo device."""

    entity_description: AttributeSensorDescription

    def __init__(
        self, coordinator: DeviceCoordinator, description: AttributeSensorDescription
    ) -> None:
        """Init AttributeSensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.conversion_state = ConversionState()

    @property
    def name_suffix(self) -> str | None:
        """Return the name of the entity."""
        return self.entity_description.name

    @property
    def unique_id_suffix(self) -> str | None:
        """Suffix to append to the WeMo device's unique ID."""
        if (suffix := self.entity_description.unique_id_suffix) is not None:
            return suffix
        return super().unique_id_suffix

    def convert_state(self, value: StateType) -> StateType | datetime:
        """Convert native state to a value appropriate for the sensor."""
        if (convert := self.entity_description.state_conversion) is None:
            return value
        return convert(self, value)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value of the device attribute."""
        return self.convert_state(getattr(self.wemo, self.entity_description.key))


class ActionSensor(AttributeSensor):
    """Sensor to read output from a UPnP Action RPC."""

    coordinator: ActionCoordinator
    entity_description: ActionSensorDescription

    @property
    def available(self) -> bool:
        """Return true if the sensor value is available."""
        return super().available and self._coordinator_value is not None

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        if not (value := self._coordinator_value):
            return None
        return self.convert_state(value)

    @property
    def _coordinator_value(self) -> str | None:
        """Return the value fetched by the coordinator."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

"""Sensors for SteamVR Base Station."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from lighthouse_ble import PowerState

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import SteamVRBaseStationConfigEntry, SteamVRBaseStationCoordinator
from .entity import SteamVRBaseStationEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SteamVRBaseStationSensorEntityDescription(SensorEntityDescription):
    """Describes a base station sensor."""

    value_fn: Callable[[SteamVRBaseStationCoordinator], StateType]


def _power_state(coordinator: SteamVRBaseStationCoordinator) -> str | None:
    power = coordinator.station.state.power
    if power is None or power is PowerState.UNKNOWN:
        return None
    return power.value


def _rssi(coordinator: SteamVRBaseStationCoordinator) -> int | None:
    if service_info := async_last_service_info(
        coordinator.hass, coordinator.address, connectable=True
    ):
        return service_info.rssi
    return None


SENSORS: tuple[SteamVRBaseStationSensorEntityDescription, ...] = (
    SteamVRBaseStationSensorEntityDescription(
        key="power_state",
        translation_key="power_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            state.value for state in PowerState if state is not PowerState.UNKNOWN
        ],
        value_fn=_power_state,
    ),
    SteamVRBaseStationSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamVRBaseStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SteamVRBaseStationSensor(coordinator, description) for description in SENSORS
    )


class SteamVRBaseStationSensor(SteamVRBaseStationEntity, SensorEntity):
    """A base station sensor."""

    entity_description: SteamVRBaseStationSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)

"""Support for sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from aiocomelit import ComelitSerialBridgeObject, ComelitVedoZoneObject
from aiocomelit.const import ALARM_ZONES, BRIDGE, OTHER, AlarmZoneState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitSerialBridge, ComelitVedoSystem


@dataclass
class ComelitVedoBaseEntityDescription:
    """Comelit VEDO entity base description."""

    value: Callable[[Any, Any], Any] = (
        lambda coordinator, key: coordinator.data.sensors[key]
    )
    is_suitable: Callable[[dict], bool] = lambda val: True


@dataclass
class ComelitVedoEntityDescription(
    ComelitVedoBaseEntityDescription, SensorEntityDescription
):
    """Comelit VEDO entity description."""


def _zone_state(coordinator: ComelitVedoSystem, zone_index: int) -> str:
    """Return current zone state."""
    zone: ComelitVedoZoneObject = coordinator.data[ALARM_ZONES][zone_index]
    return zone.human_status.value


SENSOR_BRIDGE_TYPES: Final = (
    SensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
)

SENSOR_VEDO_TYPES: Final = (
    ComelitVedoEntityDescription(
        key="human_status",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:shield-check",
        options=[zone_state.value for zone_state in AlarmZoneState],
        value=_zone_state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit sensors."""

    if config_entry.data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        await async_setup_bridge_entry(hass, config_entry, async_add_entities)
    else:
        await async_setup_vedo_entry(hass, config_entry, async_add_entities)


async def async_setup_bridge_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit Bridge sensors."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ComelitBridgeSensorEntity] = []
    for device in coordinator.data[OTHER].values():
        entities.extend(
            ComelitBridgeSensorEntity(
                coordinator, device, config_entry.entry_id, sensor_desc
            )
            for sensor_desc in SENSOR_BRIDGE_TYPES
        )
    async_add_entities(entities)


async def async_setup_vedo_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit VEDO sensors."""

    coordinator: ComelitVedoSystem = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ComelitVedoSensorEntity] = []
    for device in coordinator.data[ALARM_ZONES].values():
        entities.extend(
            ComelitVedoSensorEntity(
                coordinator, device, config_entry.entry_id, sensor_desc
            )
            for sensor_desc in SENSOR_VEDO_TYPES
        )
    async_add_entities(entities)


class ComelitBridgeSensorEntity(CoordinatorEntity[ComelitSerialBridge], SensorEntity):
    """Sensor device."""

    _attr_has_entity_name = True
    _attr_name = None
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Init sensor entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}"
        self._attr_device_info = coordinator.platform_device_info(device)

        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Sensor value."""
        return getattr(
            self.coordinator.data[OTHER][self._device.index],
            self.entity_description.key,
        )


class ComelitVedoSensorEntity(CoordinatorEntity[ComelitVedoSystem], SensorEntity):
    """Sensor device."""

    _attr_has_entity_name = True
    _attr_name = None
    entity_description: ComelitVedoEntityDescription

    def __init__(
        self,
        coordinator: ComelitVedoSystem,
        zone: ComelitVedoZoneObject,
        config_entry_entry_id: str,
        description: ComelitVedoEntityDescription,
    ) -> None:
        """Init sensor entity."""
        self._api = coordinator.api
        self._zone = zone
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{zone.index}"
        self._attr_device_info = coordinator.platform_device_info(zone)

        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Sensor value."""
        return self.entity_description.value(self.coordinator, self._zone.index)

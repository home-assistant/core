"""Support for V2C EVSE sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pytrydan import TrydanData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import V2CUpdateCoordinator
from .entity import V2CBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class V2CPowerRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[TrydanData], float]


@dataclass
class V2CPowerSensorEntityDescription(
    SensorEntityDescription, V2CPowerRequiredKeysMixin
):
    """Describes an EVSE Power sensor entity."""


POWER_SENSORS = (
    V2CPowerSensorEntityDescription(
        key="charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda evse_data: evse_data.charge_power,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up V2C sensor platform."""
    coordinator: V2CUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    evse_data = coordinator.evse.data
    assert evse_data is not None
    _LOGGER.debug("EVSE data: %s", evse_data)

    entities: list[Entity] = [
        V2CPowerSensorEntity(coordinator, description, config_entry.entry_id)
        for description in POWER_SENSORS
    ]
    async_add_entities(entities)


class V2CSensorBaseEntity(V2CBaseEntity, SensorEntity):
    """Defines a base v2c sensor entity."""


class V2CPowerSensorEntity(V2CSensorBaseEntity):
    """V2C Power sensor entity."""

    entity_description: V2CPowerSensorEntityDescription
    _attr_icon = "mdi:ev-station"

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: SensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize V2C Power entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.evse.host)},
            manufacturer="V2C",
            model="Trydan",
            name=coordinator.name,
            sw_version=coordinator.evse.firmware_version,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        assert self.data is not None
        return self.entity_description.value_fn(self.data)

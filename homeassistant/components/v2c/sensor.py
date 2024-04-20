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
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import V2CUpdateCoordinator
from .entity import V2CBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class V2CSensorEntityDescription(SensorEntityDescription):
    """Describes an EVSE Power sensor entity."""

    value_fn: Callable[[TrydanData], float]


TRYDAN_SENSORS = (
    V2CSensorEntityDescription(
        key="charge_power",
        translation_key="charge_power",
        icon="mdi:ev-station",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda evse_data: evse_data.charge_power,
    ),
    V2CSensorEntityDescription(
        key="charge_energy",
        translation_key="charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda evse_data: evse_data.charge_energy,
    ),
    V2CSensorEntityDescription(
        key="charge_time",
        translation_key="charge_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda evse_data: evse_data.charge_time,
    ),
    V2CSensorEntityDescription(
        key="house_power",
        translation_key="house_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda evse_data: evse_data.house_power,
    ),
    V2CSensorEntityDescription(
        key="fv_power",
        translation_key="fv_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda evse_data: evse_data.fv_power,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up V2C sensor platform."""
    coordinator: V2CUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        V2CSensorBaseEntity(coordinator, description, config_entry.entry_id)
        for description in TRYDAN_SENSORS
    )


class V2CSensorBaseEntity(V2CBaseEntity, SensorEntity):
    """Defines a base v2c sensor entity."""

    entity_description: V2CSensorEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: SensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize V2C Power entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.data)

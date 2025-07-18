"""AirOS Sensor component for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfDataRate,
    UnitOfFrequency,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AirOSConfigEntry
from .coordinator import AirOSDataUpdateCoordinator
from .entity import AirOSEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AirOSSensorEntityDescription(SensorEntityDescription):
    """Describe an AirOS sensor."""

    value_fn: Callable[[dict[str, Any]], StateType | None]


SENSORS: tuple[AirOSSensorEntityDescription, ...] = (
    AirOSSensorEntityDescription(
        key="host_cpuload",
        translation_key="host_cpuload",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("host", {}).get("cpuload"),
        entity_registry_enabled_default=False,
    ),
    AirOSSensorEntityDescription(
        key="host_netrole",
        translation_key="host_netrole",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        value_fn=lambda data: data.get("host", {}).get("netrole"),
    ),
    AirOSSensorEntityDescription(
        key="wireless_frequency",
        translation_key="wireless_frequency",
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("wireless", {}).get("frequency"),
    ),
    AirOSSensorEntityDescription(
        key="wireless_essid",
        translation_key="wireless_essid",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        value_fn=lambda data: data.get("wireless", {}).get("essid"),
    ),
    AirOSSensorEntityDescription(
        key="wireless_mode",
        translation_key="wireless_mode",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        value_fn=lambda data: data.get("wireless", {}).get("mode"),
    ),
    AirOSSensorEntityDescription(
        key="wireless_antenna_gain",
        translation_key="wireless_antenna_gain",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("wireless", {}).get("antenna_gain"),
    ),
    AirOSSensorEntityDescription(
        key="wireless_throughput_tx",
        translation_key="wireless_throughput_tx",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("wireless", {}).get("throughput", {}).get("tx"),
    ),
    AirOSSensorEntityDescription(
        key="wireless_throughput_rx",
        translation_key="wireless_throughput_rx",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("wireless", {}).get("throughput", {}).get("rx"),
    ),
    AirOSSensorEntityDescription(
        key="wireless_polling_dl_capacity",
        translation_key="wireless_polling_dl_capacity",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("wireless", {})
        .get("polling", {})
        .get("dl_capacity"),
    ),
    AirOSSensorEntityDescription(
        key="wireless_polling_ul_capacity",
        translation_key="wireless_polling_ul_capacity",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("wireless", {})
        .get("polling", {})
        .get("ul_capacity"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AirOS sensors from a config entry."""
    coordinator = config_entry.runtime_data

    entities = [AirOSSensor(coordinator, description) for description in SENSORS]

    async_add_entities(entities, update_before_add=False)


class AirOSSensor(AirOSEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    entity_description: AirOSSensorEntityDescription

    def __init__(
        self,
        coordinator: AirOSDataUpdateCoordinator,
        description: AirOSSensorEntityDescription,
        # station_data: dict[str, Any] | None = None,
        # station_index: int | None = None
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{self.coordinator.data.device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.device_data)

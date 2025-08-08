"""AirOS Sensor component for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from airos.data import NetRole, WirelessMode

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

from .coordinator import AirOSConfigEntry, AirOSData, AirOSDataUpdateCoordinator
from .entity import AirOSEntity

_LOGGER = logging.getLogger(__name__)

WIRELESS_MODE_OPTIONS = [mode.value.replace("-", "_").lower() for mode in WirelessMode]
NETROLE_OPTIONS = [mode.value for mode in NetRole]


@dataclass(frozen=True, kw_only=True)
class AirOSSensorEntityDescription(SensorEntityDescription):
    """Describe an AirOS sensor."""

    value_fn: Callable[[AirOSData], StateType]


SENSORS: tuple[AirOSSensorEntityDescription, ...] = (
    AirOSSensorEntityDescription(
        key="host_cpuload",
        translation_key="host_cpuload",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.host.cpuload,
        entity_registry_enabled_default=False,
    ),
    AirOSSensorEntityDescription(
        key="host_netrole",
        translation_key="host_netrole",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda data: data.host.netrole.value,
        options=NETROLE_OPTIONS,
    ),
    AirOSSensorEntityDescription(
        key="wireless_frequency",
        translation_key="wireless_frequency",
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wireless.frequency,
    ),
    AirOSSensorEntityDescription(
        key="wireless_essid",
        translation_key="wireless_essid",
        value_fn=lambda data: data.wireless.essid,
    ),
    AirOSSensorEntityDescription(
        key="wireless_antenna_gain",
        translation_key="wireless_antenna_gain",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wireless.antenna_gain,
    ),
    AirOSSensorEntityDescription(
        key="wireless_throughput_tx",
        translation_key="wireless_throughput_tx",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wireless.throughput.tx,
    ),
    AirOSSensorEntityDescription(
        key="wireless_throughput_rx",
        translation_key="wireless_throughput_rx",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wireless.throughput.rx,
    ),
    AirOSSensorEntityDescription(
        key="wireless_polling_dl_capacity",
        translation_key="wireless_polling_dl_capacity",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wireless.polling.dl_capacity,
    ),
    AirOSSensorEntityDescription(
        key="wireless_polling_ul_capacity",
        translation_key="wireless_polling_ul_capacity",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wireless.polling.ul_capacity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AirOS sensors from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(AirOSSensor(coordinator, description) for description in SENSORS)


class AirOSSensor(AirOSEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: AirOSSensorEntityDescription

    def __init__(
        self,
        coordinator: AirOSDataUpdateCoordinator,
        description: AirOSSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.derived.mac}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

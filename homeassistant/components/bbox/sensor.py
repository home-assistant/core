"""Support for Bbox sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .coordinator import BboxData, BboxRouter

type BboxConfigEntry = ConfigEntry[BboxRouter]

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BboxSensorEntityDescription(SensorEntityDescription):
    """Describes Bbox sensor entity."""

    value_fn: Callable[[BboxData], StateType | datetime]


SENSOR_DESCRIPTIONS: tuple[BboxSensorEntityDescription, ...] = (
    BboxSensorEntityDescription(
        key="down_max_bandwidth",
        translation_key="down_max_bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        icon="mdi:download",
        value_fn=lambda data: round(data.ip_stats.rx.maxBandwidth / 1000, 2),
    ),
    BboxSensorEntityDescription(
        key="up_max_bandwidth",
        translation_key="up_max_bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        icon="mdi:upload",
        value_fn=lambda data: round(data.ip_stats.tx.maxBandwidth / 1000, 2),
    ),
    BboxSensorEntityDescription(
        key="current_down_bandwidth",
        translation_key="down_stream",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:download",
        value_fn=lambda data: round(data.ip_stats.rx.bandwidth / 1000, 2),
    ),
    BboxSensorEntityDescription(
        key="current_up_bandwidth",
        translation_key="up_stream",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:upload",
        value_fn=lambda data: round(data.ip_stats.tx.bandwidth / 1000, 2),
    ),
    BboxSensorEntityDescription(
        key="number_of_reboots",
        translation_key="number_of_reboots",
        icon="mdi:restart",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.router_info.numberofboots,
    ),
    BboxSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
        value_fn=lambda data: (utcnow() - timedelta(seconds=data.router_info.uptime)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bbox sensor entries."""
    coordinator = entry.runtime_data

    async_add_entities(
        BboxSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class BboxSensor(CoordinatorEntity[BboxRouter], SensorEntity):
    """Representation of a Bbox sensor."""

    entity_description: BboxSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BboxRouter,
        description: BboxSensorEntityDescription,
        entry: BboxConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        router_info = coordinator.data.router_info
        self._attr_unique_id = f"{router_info.serialnumber}_{description.key}"

        model = router_info.modelname
        sw_version = router_info.main.version
        identifiers = {(DOMAIN, router_info.serialnumber)}

        self._attr_device_info = DeviceInfo(
            identifiers=identifiers,
            name="Bbox",
            manufacturer="Bouygues Telecom",
            model=model,
            sw_version=sw_version,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

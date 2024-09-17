"""Creates the sensor entities for the mower."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from aiotainer.model import NodeData, Container

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import PortainerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)

ATTR_WORK_AREA_ID_ASSIGNMENT = "work_area_id_assignment"


STATE_NO_WORK_AREA_ACTIVE = "no_work_area_active"


@dataclass(frozen=True, kw_only=True)
class AutomowerSensorEntityDescription(SensorEntityDescription):
    """Describes Automower sensor entity."""

    exists_fn: Callable[[NodeData], bool] = lambda _: True
    extra_state_attributes_fn: Callable[[NodeData], Mapping[str, Any] | None] = (
        lambda _: None
    )
    option_fn: Callable[[NodeData], list[str] | None] = lambda _: None
    value_fn: Callable[[Container], StateType | datetime]


SENSOR_TYPES: tuple[AutomowerSensorEntityDescription, ...] = (
    AutomowerSensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda data: data.state.name.lower(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data
    for node_id in coordinator.data:
        for snapshot in coordinator.data[node_id].snapshots:
            for container in snapshot.docker_snapshot_raw.containers:
                async_add_entities(
                    AutomowerSensorEntity(
                        node_id, snapshot, container, coordinator, description
                    )
                    for description in SENSOR_TYPES
                    if description.exists_fn(coordinator.data[node_id])
                )


class AutomowerSensorEntity(AutomowerBaseEntity, SensorEntity):
    """Defining the Automower Sensors with AutomowerSensorEntityDescription."""

    entity_description: AutomowerSensorEntityDescription
    _unrecorded_attributes = frozenset({ATTR_WORK_AREA_ID_ASSIGNMENT})

    def __init__(
        self,
        mower_id: str,
        snapshot: str,
        container: Container,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerSensorEntityDescription,
    ) -> None:
        """Set up AutomowerSensors."""
        super().__init__(mower_id, container, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}-{container}-{description.key}"
        _LOGGER.debug("self.mower_attributes %s", self.mower_attributes)
        self.container = container
        self._attr_translation_placeholders = {
            "container": container.names[0].strip("/").capitalize()
        }

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        _LOGGER.debug("self.mower_attributes %s", self.mower_attributes)
        return self.entity_description.value_fn(self.container_attributes)

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.option_fn(self.mower_attributes)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return self.entity_description.extra_state_attributes_fn(self.mower_attributes)

"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging
from typing import Union

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SENSOR_TYPE_RAINDELAY, SENSOR_TYPE_RAINSENSOR
from .coordinator import RainbirdUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TYPE_RAINSENSOR,
        name="Rainsensor",
        icon="mdi:water",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_RAINDELAY,
        name="Raindelay",
        icon="mdi:water-off",
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Rain Bird sensor."""

    if discovery_info is None:
        return

    async_add_entities(
        [
            RainBirdSensor(discovery_info[description.key], description)
            for description in SENSOR_TYPES
        ],
        True,
    )


class RainBirdSensor(
    CoordinatorEntity[RainbirdUpdateCoordinator[Union[int, bool]]], SensorEntity
):
    """A sensor implementation for Rain Bird device."""

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator[int | bool],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data

"""Support for Rain Bird Irrigation system LNK Wi-Fi Module."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import RainbirdUpdateCoordinator
from .types import RainbirdConfigEntry

_LOGGER = logging.getLogger(__name__)


RAIN_DELAY_ENTITY_DESCRIPTION = SensorEntityDescription(
    key="raindelay",
    translation_key="raindelay",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RainbirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird sensor."""
    async_add_entities(
        [
            RainBirdSensor(
                config_entry.runtime_data.coordinator,
                RAIN_DELAY_ENTITY_DESCRIPTION,
            )
        ]
    )


class RainBirdSensor(CoordinatorEntity[RainbirdUpdateCoordinator], SensorEntity):
    """A sensor implementation for Rain Bird device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if coordinator.unique_id is not None:
            self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
            self._attr_device_info = coordinator.device_info
        else:
            self._attr_name = (
                f"{coordinator.device_name} {description.key.capitalize()}"
            )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data.rain_delay

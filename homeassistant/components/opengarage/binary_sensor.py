"""Platform for the opengarage.io binary sensor component."""

import logging
from typing import cast, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenGarageConfigEntry, OpenGarageDataUpdateCoordinator
from .entity import (
    OpenGarageCapabilityEntity,
    OpenGarageEntity,
    async_add_capability_entities,
)

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="vehicle",
        translation_key="vehicle",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenGarageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenGarage binary sensors."""
    open_garage_data_coordinator = entry.runtime_data
    async_add_entities(
        OpenGarageBinarySensor(
            open_garage_data_coordinator,
            cast(str, entry.unique_id),
            description,
        )
        for description in SENSOR_TYPES
    )

    async_add_capability_entities(
        entry.runtime_data,
        async_add_entities,
        {
            "obstruction": lambda: OpenGarageObstructionSensor(
                entry.runtime_data,
                cast(str, entry.unique_id),
                BinarySensorEntityDescription(
                    key="obstruction",
                    translation_key="obstruction",
                    device_class=BinarySensorDeviceClass.SAFETY,
                ),
            )
        },
    )


class OpenGarageBinarySensor(OpenGarageEntity, BinarySensorEntity):
    """Representation of a OpenGarage binary sensor."""

    def __init__(
        self,
        coordinator: OpenGarageDataUpdateCoordinator,
        device_id: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self._available = False
        super().__init__(coordinator, device_id, description)

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._available

    @callback
    @override
    def _update_attr(self) -> None:
        """Handle updated data from the coordinator."""
        state = self.coordinator.data.raw.get(self.entity_description.key)
        if state == 1:
            self._attr_is_on = True
            self._available = True
        elif state == 0:
            self._attr_is_on = False
            self._available = True
        else:
            self._available = False


class OpenGarageObstructionSensor(OpenGarageCapabilityEntity, BinarySensorEntity):
    """Representation of the opener's obstruction detector."""

    capability = "obstruction"

    @callback
    @override
    def _update_attr(self) -> None:
        """Update the reported obstruction state."""
        self._attr_is_on = self.coordinator.data.obstruction

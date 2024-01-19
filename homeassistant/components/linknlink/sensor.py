"""Support for linknlink sensors."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LinknLinkCoordinator
from .entity import LinknLinkEntity

_LOGGER = logging.getLogger(__name__)

HUMITURE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="envtemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="envhumid",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the linknlink sensor."""

    coordinator: LinknLinkCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        LinknLinkSensor(coordinator, description) for description in HUMITURE_SENSORS
    )


class LinknLinkSensor(LinknLinkEntity, SensorEntity):
    """Representation of a linknlink sensor."""

    def __init__(
        self,
        coordinator: LinknLinkCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{coordinator.api.mac.hex()}-{description.key}"
        self._update_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self._update_attr()
        super()._handle_coordinator_update()

    @callback
    def _update_attr(self) -> None:
        """Update attributes for sensor."""
        try:
            self._attr_native_value = float(
                self.coordinator.data[self.entity_description.key]
            )
        except KeyError:
            _LOGGER.error(
                "Failed get the value of key: %s", self.entity_description.key
            )

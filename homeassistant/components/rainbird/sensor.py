"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging
from typing import Union

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPE_RAINDELAY
from .coordinator import RainbirdUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


RAIN_DELAY_ENTITY_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_TYPE_RAINDELAY,
    name="Raindelay",
    icon="mdi:water-off",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = RainbirdUpdateCoordinator(
        hass, "Rain delay", data.controller.get_rain_delay
    )
    await coordinator.async_config_entry_first_refresh()
    async_add_entities(
        [
            RainBirdSensor(
                coordinator,
                RAIN_DELAY_ENTITY_DESCRIPTION,
                data.serial_number,
                data.device_info,
            )
        ]
    )


class RainBirdSensor(
    CoordinatorEntity[RainbirdUpdateCoordinator[Union[int, bool]]], SensorEntity
):
    """A sensor implementation for Rain Bird device."""

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator[int | bool],
        description: SensorEntityDescription,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}-{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data

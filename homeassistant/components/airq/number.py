"""Definition of air-Q number platform used to control the LED strips."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirQConfigEntry, AirQCoordinator

_LOGGER = logging.getLogger(__name__)
LED_VALUE_DEFAULT = 6.0


AIRQ_LED_BRIGHTNESS = NumberEntityDescription(
    key="airq_led_brightness",
    translation_key="airq_led_brightness",
    native_min_value=0.0,
    native_max_value=10.0,
    native_step=0.1,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities: a single entity for the LEDs."""

    coordinator = entry.runtime_data
    entities = [AirQLEDBrightness(coordinator, AIRQ_LED_BRIGHTNESS)]

    async_add_entities(entities)


class AirQLEDBrightness(CoordinatorEntity[AirQCoordinator], NumberEntity):
    """Representation of the LEDs from a single AirQ."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirQCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize a single sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> float:
        """Return the state of the number."""
        return float(self.coordinator.data.get("brightness", LED_VALUE_DEFAULT))

    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        _LOGGER.debug(
            "Changing LED brighntess from %.1f to %.1f",
            self.coordinator.data["brightness"],
            value,
        )
        self.coordinator.data["brightness"] = value
        self.async_write_ha_state()
        await self.coordinator.airq.set_current_brightness(value)

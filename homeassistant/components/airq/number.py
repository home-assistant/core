"""Definition of air-Q number platform used to control the LED strips."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from aioairq.core import AirQ

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirQConfigEntry, AirQCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AirQBrightnessDescription(NumberEntityDescription):
    """Describes AirQ number entity responsible for brightness control."""

    value: Callable[[dict], float]
    set_value: Callable[[AirQ, float], Awaitable[None]]


AIRQ_LED_BRIGHTNESS = AirQBrightnessDescription(
    key="airq_led_brightness",
    translation_key="airq_led_brightness",
    native_min_value=0.0,
    native_max_value=100.0,
    native_step=1.0,
    native_unit_of_measurement=PERCENTAGE,
    value=lambda data: data["brightness"],
    set_value=lambda device, value: device.set_current_brightness(value),
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
        description: AirQBrightnessDescription,
    ) -> None:
        """Initialize a single sensor."""
        super().__init__(coordinator)
        self.entity_description: AirQBrightnessDescription = description

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> float:
        """Return the brightness of the LEDs in %."""
        return self.entity_description.value(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set the brightness of the LEDs to the value in %."""
        _LOGGER.debug(
            "Changing LED brighntess from %.0f%% to %.0f%%",
            self.coordinator.data["brightness"],
            value,
        )
        await self.entity_description.set_value(self.coordinator.airq, value)
        await self.coordinator.async_request_refresh()

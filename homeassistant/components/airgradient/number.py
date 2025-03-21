"""Support for AirGradient number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from airgradient import AirGradientClient, Config
from airgradient.models import ConfigurationControl

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirGradientConfigEntry
from .const import DOMAIN
from .coordinator import AirGradientCoordinator
from .entity import AirGradientEntity, exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AirGradientNumberEntityDescription(NumberEntityDescription):
    """Describes AirGradient number entity."""

    value_fn: Callable[[Config], int]
    set_value_fn: Callable[[AirGradientClient, int], Awaitable[None]]


DISPLAY_BRIGHTNESS = AirGradientNumberEntityDescription(
    key="display_brightness",
    translation_key="display_brightness",
    entity_category=EntityCategory.CONFIG,
    native_min_value=0,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=PERCENTAGE,
    value_fn=lambda config: config.display_brightness,
    set_value_fn=lambda client, value: client.set_display_brightness(value),
)

LED_BAR_BRIGHTNESS = AirGradientNumberEntityDescription(
    key="led_bar_brightness",
    translation_key="led_bar_brightness",
    entity_category=EntityCategory.CONFIG,
    native_min_value=0,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=PERCENTAGE,
    value_fn=lambda config: config.led_bar_brightness,
    set_value_fn=lambda client, value: client.set_led_bar_brightness(value),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirGradientConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirGradient number entities based on a config entry."""

    coordinator = entry.runtime_data
    model = coordinator.data.measures.model

    added_entities = False

    @callback
    def _async_check_entities() -> None:
        nonlocal added_entities

        if (
            coordinator.data.config.configuration_control is ConfigurationControl.LOCAL
            and not added_entities
        ):
            entities = []
            if "I" in model:
                entities.append(AirGradientNumber(coordinator, DISPLAY_BRIGHTNESS))
            if "L" in model:
                entities.append(AirGradientNumber(coordinator, LED_BAR_BRIGHTNESS))

            async_add_entities(entities)
            added_entities = True
        elif (
            coordinator.data.config.configuration_control
            is not ConfigurationControl.LOCAL
            and added_entities
        ):
            entity_registry = er.async_get(hass)
            for entity_description in (DISPLAY_BRIGHTNESS, LED_BAR_BRIGHTNESS):
                unique_id = f"{coordinator.serial_number}-{entity_description.key}"
                if entity_id := entity_registry.async_get_entity_id(
                    NUMBER_DOMAIN, DOMAIN, unique_id
                ):
                    entity_registry.async_remove(entity_id)
            added_entities = False

    coordinator.async_add_listener(_async_check_entities)
    _async_check_entities()


class AirGradientNumber(AirGradientEntity, NumberEntity):
    """Defines an AirGradient number entity."""

    entity_description: AirGradientNumberEntityDescription

    def __init__(
        self,
        coordinator: AirGradientCoordinator,
        description: AirGradientNumberEntityDescription,
    ) -> None:
        """Initialize AirGradient number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.coordinator.data.config)

    @exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        await self.entity_description.set_value_fn(self.coordinator.client, int(value))
        await self.coordinator.async_request_refresh()

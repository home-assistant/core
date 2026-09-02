"""Support for AirGradient number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from airgradient import AirGradientClient, Config
from airgradient.models import ConfigurationControl

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfRatio
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirGradientConfigEntry
from .const import (
    DISPLAY_BRIGHTNESS as DISPLAY_BRIGHTNESS_CONFIG,
    DOMAIN,
    supports_config,
)
from .coordinator import AirGradientCoordinator
from .entity import AirGradientEntity, exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AirGradientNumberEntityDescription(NumberEntityDescription):
    """Describes AirGradient number entity."""

    config_key: str
    value_fn: Callable[[Config], int | None]
    set_value_fn: Callable[[AirGradientClient, int], Awaitable[None]]


DISPLAY_BRIGHTNESS = AirGradientNumberEntityDescription(
    key="display_brightness",
    translation_key="display_brightness",
    entity_category=EntityCategory.CONFIG,
    native_min_value=0,
    native_max_value=100,
    native_step=1,
    native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
    config_key=DISPLAY_BRIGHTNESS_CONFIG,
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
    native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
    config_key="led_bar_brightness",
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
    descriptions = (DISPLAY_BRIGHTNESS, LED_BAR_BRIGHTNESS)
    descriptions_by_key = {description.key: description for description in descriptions}
    added_entities: set[str] = set()

    @callback
    def _async_check_entities() -> None:
        nonlocal added_entities
        config = coordinator.data.config
        desired_entities = {
            description.key
            for description in descriptions
            if config.configuration_control is ConfigurationControl.LOCAL
            and supports_config(
                model, coordinator.client.api_version, config, description.config_key
            )
        }

        if entities_to_add := desired_entities - added_entities:
            async_add_entities(
                [
                    AirGradientNumber(coordinator, descriptions_by_key[key])
                    for key in entities_to_add
                ]
            )
        if entities_to_remove := added_entities - desired_entities:
            entity_registry = er.async_get(hass)
            for key in entities_to_remove:
                unique_id = f"{coordinator.serial_number}-{key}"
                if entity_id := entity_registry.async_get_entity_id(
                    NUMBER_DOMAIN, DOMAIN, unique_id
                ):
                    entity_registry.async_remove(entity_id)
        added_entities = desired_entities

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
    @override
    def native_value(self) -> int | None:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.coordinator.data.config)

    @exception_handler
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        await self.entity_description.set_value_fn(self.coordinator.client, int(value))
        await self.coordinator.async_request_refresh()

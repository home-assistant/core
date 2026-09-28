"""Support for AirGradient buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from airgradient import AirGradientClient, ConfigurationControl

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirGradientConfigEntry
from .const import DOMAIN, supports_action
from .coordinator import AirGradientCoordinator
from .entity import AirGradientEntity, exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AirGradientButtonEntityDescription(ButtonEntityDescription):
    """Describes AirGradient button entity."""

    press_fn: Callable[[AirGradientClient], Awaitable[None]]


CO2_CALIBRATION = AirGradientButtonEntityDescription(
    key="co2_calibration",
    translation_key="co2_calibration",
    entity_category=EntityCategory.CONFIG,
    press_fn=lambda client: client.request_co2_calibration(),
)
LED_BAR_TEST = AirGradientButtonEntityDescription(
    key="led_bar_test",
    translation_key="led_bar_test",
    entity_category=EntityCategory.CONFIG,
    press_fn=lambda client: client.request_led_bar_test(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirGradientConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirGradient button entities based on a config entry."""
    coordinator = entry.runtime_data
    model = coordinator.data.measures.model
    descriptions = (CO2_CALIBRATION, LED_BAR_TEST)
    descriptions_by_key = {description.key: description for description in descriptions}
    added_entities: set[str] = set()

    @callback
    def _check_entities() -> None:
        nonlocal added_entities
        desired_entities = {
            description.key
            for description in descriptions
            if coordinator.data.config.configuration_control
            is ConfigurationControl.LOCAL
            and supports_action(model, description.key)
        }

        if entities_to_add := desired_entities - added_entities:
            async_add_entities(
                [
                    AirGradientButton(coordinator, descriptions_by_key[key])
                    for key in entities_to_add
                ]
            )
        if entities_to_remove := added_entities - desired_entities:
            entity_registry = er.async_get(hass)
            for key in entities_to_remove:
                unique_id = f"{coordinator.serial_number}-{key}"
                if entity_id := entity_registry.async_get_entity_id(
                    BUTTON_DOMAIN, DOMAIN, unique_id
                ):
                    entity_registry.async_remove(entity_id)
        added_entities = desired_entities

    coordinator.async_add_listener(_check_entities)
    _check_entities()


class AirGradientButton(AirGradientEntity, ButtonEntity):
    """Defines an AirGradient button."""

    entity_description: AirGradientButtonEntityDescription

    def __init__(
        self,
        coordinator: AirGradientCoordinator,
        description: AirGradientButtonEntityDescription,
    ) -> None:
        """Initialize airgradient button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"

    @exception_handler
    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.coordinator.client)

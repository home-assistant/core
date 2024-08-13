"""Support for AirGradient buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from airgradient import AirGradientClient, ConfigurationControl

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, AirGradientConfigEntry
from .coordinator import AirGradientConfigCoordinator
from .entity import AirGradientEntity


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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirGradient button entities based on a config entry."""
    model = entry.runtime_data.measurement.data.model
    coordinator = entry.runtime_data.config

    added_entities = False

    @callback
    def _check_entities() -> None:
        nonlocal added_entities

        if (
            coordinator.data.configuration_control is ConfigurationControl.LOCAL
            and not added_entities
        ):
            entities = [AirGradientButton(coordinator, CO2_CALIBRATION)]
            if "L" in model:
                entities.append(AirGradientButton(coordinator, LED_BAR_TEST))

            async_add_entities(entities)
            added_entities = True
        elif (
            coordinator.data.configuration_control is not ConfigurationControl.LOCAL
            and added_entities
        ):
            entity_registry = er.async_get(hass)
            for entity_description in (CO2_CALIBRATION, LED_BAR_TEST):
                unique_id = f"{coordinator.serial_number}-{entity_description.key}"
                if entity_id := entity_registry.async_get_entity_id(
                    BUTTON_DOMAIN, DOMAIN, unique_id
                ):
                    entity_registry.async_remove(entity_id)
            added_entities = False

    coordinator.async_add_listener(_check_entities)
    _check_entities()


class AirGradientButton(AirGradientEntity, ButtonEntity):
    """Defines an AirGradient button."""

    entity_description: AirGradientButtonEntityDescription
    coordinator: AirGradientConfigCoordinator

    def __init__(
        self,
        coordinator: AirGradientConfigCoordinator,
        description: AirGradientButtonEntityDescription,
    ) -> None:
        """Initialize airgradient button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.coordinator.client)

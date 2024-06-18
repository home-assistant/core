"""Support for AirGradient buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from airgradient import AirGradientClient

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirGradientConfigEntry
from .coordinator import AirGradientConfigCoordinator
from .entity import AirGradientEntity


@dataclass(frozen=True, kw_only=True)
class AirGradientButtonEntityDescription(ButtonEntityDescription):
    """Describes AirGradient button entity."""

    press_fn: Callable[[AirGradientClient], Awaitable[None]]


CO2_CALIBRATION = AirGradientButtonEntityDescription(
    key="co2_calibration",
    translation_key="co2_calibration",
    press_fn=lambda client: client.request_co2_calibration(),
)
LED_BAR_TEST = AirGradientButtonEntityDescription(
    key="led_bar_test",
    translation_key="led_bar_test",
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

    entities = [AirGradientButton(coordinator, CO2_CALIBRATION)]
    if "L" in model:
        entities.append(AirGradientButton(coordinator, LED_BAR_TEST))

    async_add_entities(entities)


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

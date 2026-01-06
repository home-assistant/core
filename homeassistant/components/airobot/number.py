"""Number platform for Airobot thermostat."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pyairobotrest.const import HYSTERESIS_BAND_MAX, HYSTERESIS_BAND_MIN
from pyairobotrest.exceptions import AirobotError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirobotConfigEntry
from .const import DOMAIN
from .coordinator import AirobotDataUpdateCoordinator
from .entity import AirobotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirobotNumberEntityDescription(NumberEntityDescription):
    """Describes Airobot number entity."""

    value_fn: Callable[[AirobotDataUpdateCoordinator], float]
    set_value_fn: Callable[[AirobotDataUpdateCoordinator, float], Awaitable[None]]


NUMBERS: tuple[AirobotNumberEntityDescription, ...] = (
    AirobotNumberEntityDescription(
        key="hysteresis_band",
        translation_key="hysteresis_band",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=HYSTERESIS_BAND_MIN / 10.0,
        native_max_value=HYSTERESIS_BAND_MAX / 10.0,
        native_step=0.1,
        value_fn=lambda coordinator: coordinator.data.settings.hysteresis_band,
        set_value_fn=lambda coordinator, value: coordinator.client.set_hysteresis_band(
            value
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Airobot number platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirobotNumber(coordinator, description) for description in NUMBERS
    )


class AirobotNumber(AirobotEntity, NumberEntity):
    """Representation of an Airobot number entity."""

    entity_description: AirobotNumberEntityDescription

    def __init__(
        self,
        coordinator: AirobotDataUpdateCoordinator,
        description: AirobotNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.status.device_id}_{description.key}"

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        try:
            await self.entity_description.set_value_fn(self.coordinator, value)
        except AirobotError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_value_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        else:
            await self.coordinator.async_request_refresh()

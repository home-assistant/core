"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_CURRENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import InvalidAuth, WallboxCoordinator, WallboxData
from .const import CONF_MAX_AVAILABLE_POWER_KEY, CONF_MAX_CHARGING_CURRENT_KEY, DOMAIN


@dataclass
class WallboxRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[WallboxData], int | float]
    max_value_fn: Callable[[WallboxData], int | float]


@dataclass
class WallboxNumberEntityDescription(NumberEntityDescription, WallboxRequiredKeysMixin):
    """Describes Wallbox sensor entity."""

    min_value: float = 0


NUMBER_TYPES: dict[str, WallboxNumberEntityDescription] = {
    CONF_MAX_CHARGING_CURRENT_KEY: WallboxNumberEntityDescription(
        key=CONF_MAX_CHARGING_CURRENT_KEY,
        name="Max. Charging Current",
        device_class=DEVICE_CLASS_CURRENT,
        min_value=6,
        value_fn=lambda data: data[CONF_MAX_CHARGING_CURRENT_KEY],
        max_value_fn=lambda data: data[CONF_MAX_AVAILABLE_POWER_KEY],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create wallbox sensor entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Check if the user is authorized to change current, if so, add number component:
    try:
        await coordinator.async_set_charging_current(
            coordinator.data[CONF_MAX_CHARGING_CURRENT_KEY]
        )
    except InvalidAuth:
        return

    async_add_entities(
        [
            WallboxNumber(coordinator, entry, description)
            for ent in coordinator.data
            if (description := NUMBER_TYPES.get(ent))
        ]
    )


class WallboxNumber(CoordinatorEntity, NumberEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxNumberEntityDescription
    coordinator: WallboxCoordinator

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        entry: ConfigEntry,
        description: WallboxNumberEntityDescription,
    ) -> None:
        """Initialize a Wallbox sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{entry.title} {description.name}"
        self._attr_min_value = description.min_value

    @property
    def max_value(self) -> float:
        """Return the maximum available current."""
        return self.entity_description.max_value_fn(self.coordinator.data)

    @property
    def value(self) -> float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_value(self, value: float) -> None:
        """Set the value of the entity."""
        await self.coordinator.async_set_charging_current(value)

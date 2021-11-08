"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import DEVICE_CLASS_CURRENT
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import InvalidAuth
from .const import (
    CONF_CONNECTIONS,
    CONF_MAX_AVAILABLE_POWER_KEY,
    CONF_MAX_CHARGING_CURRENT_KEY,
    DOMAIN,
)


@dataclass
class WallboxNumberEntityDescription(NumberEntityDescription):
    """Describes Wallbox sensor entity."""

    min_value: float = 0


NUMBER_TYPES: dict[str, WallboxNumberEntityDescription] = {
    CONF_MAX_CHARGING_CURRENT_KEY: WallboxNumberEntityDescription(
        key=CONF_MAX_CHARGING_CURRENT_KEY,
        name="Max. Charging Current",
        device_class=DEVICE_CLASS_CURRENT,
        min_value=6,
    ),
}


async def async_setup_entry(hass, config, async_add_entities):
    """Create wallbox sensor entities in HASS."""
    coordinator = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]

    # Check if the user is authorized to change current, if so, add number component:
    try:
        await coordinator.async_set_charging_current(
            coordinator.data[CONF_MAX_CHARGING_CURRENT_KEY]
        )
    except InvalidAuth:
        return

    async_add_entities(
        [
            WallboxNumber(coordinator, config, description)
            for ent in coordinator.data
            if (description := NUMBER_TYPES.get(ent))
        ]
    )


class WallboxNumber(CoordinatorEntity, NumberEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxNumberEntityDescription

    def __init__(
        self, coordinator, config, description: WallboxNumberEntityDescription
    ):
        """Initialize a Wallbox sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_name = f"{config.title} {description.name}"
        self._attr_min_value = description.min_value

    @property
    def max_value(self):
        """Return the maximum available current."""
        return self._coordinator.data[CONF_MAX_AVAILABLE_POWER_KEY]

    @property
    def value(self):
        """Return the state of the sensor."""
        return self._coordinator.data[CONF_MAX_CHARGING_CURRENT_KEY]

    async def async_set_value(self, value: float):
        """Set the value of the entity."""
        await self._coordinator.async_set_charging_current(value)

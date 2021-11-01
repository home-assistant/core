"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import InvalidAuth
from .const import (
    CONF_CONNECTIONS,
    CONF_MAX_AVAILABLE_POWER_KEY,
    CONF_MAX_CHARGING_CURRENT_KEY,
    DOMAIN,
    NUMBER_TYPES,
    WallboxNumberEntityDescription,
)


async def async_setup_entry(hass, config, async_add_entities):
    """Create wallbox sensor entities in HASS."""
    coordinator = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]

    filtered_data = {
        k: coordinator.data[k] for k in NUMBER_TYPES if k in coordinator.data
    }
    # Check if the user is authorized to change current, if so, add number component:
    try:
        await coordinator.async_set_charging_current(
            coordinator.data[CONF_MAX_CHARGING_CURRENT_KEY]
        )
    except InvalidAuth:
        pass
    else:
        async_add_entities(
            [
                WallboxNumber(coordinator, config, description)
                for ent in filtered_data
                if (description := NUMBER_TYPES[ent])
            ]
        )


class WallboxNumber(CoordinatorEntity, NumberEntity):
    """Representation of the Wallbox portal."""

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

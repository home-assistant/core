"""Number platform for Advantage Air integration."""

from homeassistant.components.number import NumberEntity
from homeassistant.const import ENTITY_CATEGORY_CONFIG, TIME_MINUTES

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir toggle platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    for ac_key in instance["coordinator"].data["aircons"]:
        entities.append(AdvantageAirTimeTo(instance, ac_key, "On"))
        entities.append(AdvantageAirTimeTo(instance, ac_key, "Off"))
    async_add_entities(entities)


class AdvantageAirTimeTo(AdvantageAirEntity, NumberEntity):
    """Representation of Advantage Air TimeTo number."""

    _attr_unit_of_measurement = TIME_MINUTES
    _attr_entity_category = ENTITY_CATEGORY_CONFIG
    _attr_step = 1
    _attr_min_value = 0
    _attr_max_value = 720

    def __init__(self, instance: str, ac_key: str, action: str) -> None:
        """Initialize the Advantage Air timer number."""
        super().__init__(instance, ac_key)
        self._time_key = f"countDownTo{action}"
        self._attr_name = f'{self._ac["name"]} Time To {action}'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-timeto{action}'
        )

    @property
    def value(self):
        """Return the current value."""
        return self._ac.get(self._time_key)

    @property
    def icon(self):
        """Return a representative icon of the timer."""
        if self._ac.get(self._time_key) > 0:
            return "mdi:timer-outline"
        return "mdi:timer-off-outline"

    async def async_set_value(self, value: float):
        """Set the timer value."""
        await self.async_change({self.ac_key: {"info": {self._time_key: int(value)}}})

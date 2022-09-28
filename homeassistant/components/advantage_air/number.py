"""Number platform for Advantage Air integration."""
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TIME_MINUTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirAcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir number platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    for ac_key in instance["coordinator"].data["aircons"]:
        entities.append(AdvantageAirTimeTo(instance, ac_key, "On"))
        entities.append(AdvantageAirTimeTo(instance, ac_key, "Off"))
    async_add_entities(entities)


class AdvantageAirTimeTo(AdvantageAirAcEntity, NumberEntity):
    """Representation of Advantage Air TimeTo number."""

    _attr_native_unit_of_measurement = TIME_MINUTES
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1
    _attr_native_min_value = 0
    _attr_native_max_value = 720

    def __init__(self, instance: dict[str, Any], ac_key: str, action: str) -> None:
        """Initialize the Advantage Air timer number."""
        super().__init__(instance, ac_key)
        self._time_key = f"countDownTo{action}"
        self._attr_name = f"Time to {action}"
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-timeto{action}'
        )

    @property
    def native_value(self):
        """Return the current value."""
        return self._ac.get(self._time_key)

    @property
    def icon(self):
        """Return a representative icon of the timer."""
        if self._ac.get(self._time_key) > 0:
            return "mdi:timer-outline"
        return "mdi:timer-off-outline"

    async def async_set_native_value(self, value: float) -> None:
        """Set the timer value."""
        await self.aircon({self.ac_key: {"info": {self._time_key: int(value)}}})

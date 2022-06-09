"""Support for a ScreenLogic number entity."""
import logging

from screenlogicpy.const import BODY_TYPE, DATA as SL_DATA, EQUIPMENT, SCG

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

SUPPORTED_SCG_NUMBERS = (
    "scg_level1",
    "scg_level2",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    equipment_flags = coordinator.data[SL_DATA.KEY_CONFIG]["equipment_flags"]
    if equipment_flags & EQUIPMENT.FLAG_CHLORINATOR:
        async_add_entities(
            [
                ScreenLogicNumber(coordinator, scg_level)
                for scg_level in coordinator.data[SL_DATA.KEY_SCG]
                if scg_level in SUPPORTED_SCG_NUMBERS
            ]
        )


class ScreenLogicNumber(ScreenlogicEntity, NumberEntity):
    """Class to represent a ScreenLogic Number."""

    def __init__(self, coordinator, data_key, enabled=True):
        """Initialize of the entity."""
        super().__init__(coordinator, data_key, enabled)
        self._body_type = SUPPORTED_SCG_NUMBERS.index(self._data_key)
        self._attr_max_value = SCG.LIMIT_FOR_BODY[self._body_type]
        self._attr_name = f"{self.gateway_name} {self.sensor['name']}"
        self._attr_unit_of_measurement = self.sensor["unit"]

    @property
    def value(self) -> float:
        """Return the current value."""
        return self.sensor["value"]

    async def async_set_value(self, value: float) -> None:
        """Update the current value."""
        # Need to set both levels at the same time, so we gather
        # both existing level values and override the one that changed.
        levels = {}
        for level in SUPPORTED_SCG_NUMBERS:
            levels[level] = self.coordinator.data[SL_DATA.KEY_SCG][level]["value"]
        levels[self._data_key] = int(value)

        if await self.coordinator.gateway.async_set_scg_config(
            levels[SUPPORTED_SCG_NUMBERS[BODY_TYPE.POOL]],
            levels[SUPPORTED_SCG_NUMBERS[BODY_TYPE.SPA]],
        ):
            _LOGGER.debug(
                "Set SCG to %i, %i",
                levels[SUPPORTED_SCG_NUMBERS[BODY_TYPE.POOL]],
                levels[SUPPORTED_SCG_NUMBERS[BODY_TYPE.SPA]],
            )
            await self._async_refresh()
        else:
            _LOGGER.warning(
                "Failed to set_scg to %i, %i",
                levels[SUPPORTED_SCG_NUMBERS[BODY_TYPE.POOL]],
                levels[SUPPORTED_SCG_NUMBERS[BODY_TYPE.SPA]],
            )

    @property
    def sensor(self) -> dict:
        """Shortcut to access the level sensor data."""
        return self.coordinator.data[SL_DATA.KEY_SCG][self._data_key]

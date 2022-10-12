"""Support for hunterdouglass_powerview settings."""
import logging

from aiopvapi.resources.shade import BaseShade, factory as PvShade

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY_KIND,
    DOMAIN,
    POWER_SUPPLY_TYPE,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    SHADE_BATTERY_LEVEL,
)
from .entity import ShadeEntity
from .model import PowerviewEntryData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas shades settings."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for raw_shade in pv_entry.shade_data.values():
        shade: BaseShade = PvShade(raw_shade, pv_entry.api)
        if SHADE_BATTERY_LEVEL not in shade.raw_data:
            continue
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = pv_entry.room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")
        entities.append(
            PowerViewShadePowerSource(
                pv_entry.coordinator,
                pv_entry.device_info,
                room_name,
                shade,
                name_before_refresh,
            )
        )
    async_add_entities(entities)


class PowerViewShadePowerSource(ShadeEntity, SelectEntity):
    """Representation of the type of battery used to power the shade."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:power-plug-outline"

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_unique_id = f"{self._attr_unique_id}_powersource"
        self._attr_name = f"{self._shade_name} Power Source"
        self._attr_options = list(POWER_SUPPLY_TYPE)

    @property
    def current_option(self) -> str:
        """Return the current selected value."""
        battery_type = self._shade.raw_data.get(ATTR_BATTERY_KIND)
        if battery_type not in POWER_SUPPLY_TYPE.values():
            return ""
        return list(POWER_SUPPLY_TYPE.keys())[
            list(POWER_SUPPLY_TYPE.values()).index(battery_type)
        ]

    async def async_select_option(self, option: str) -> None:
        """Set power source in the hub."""
        _LOGGER.debug("Power supply set to: %s (%s)", option, POWER_SUPPLY_TYPE[option])
        await self._shade.set_power_source(POWER_SUPPLY_TYPE[option])

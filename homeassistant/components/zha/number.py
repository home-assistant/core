"""Support for ZHA AnalogOutput cluster."""

from __future__ import annotations

import functools
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UndefinedType

from .entity import ZHAEntity
from .helpers import SIGNAL_ADD_ENTITIES, get_zha_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation Analog Output from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.NUMBER, [])
    entities = [ZhaNumber(entity_data) for entity_data in entities_to_create]
    async_add_entities(entities)

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(async_add_entities, entities_to_create),
    )
    config_entry.async_on_unload(unsub)


class ZhaNumber(ZHAEntity, NumberEntity):
    """Representation of a ZHA Number entity."""

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_data.entity.native_value

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.entity_data.entity.native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.entity_data.entity.native_max_value

    @property
    def native_step(self) -> float | None:
        """Return the value step."""
        return self.entity_data.entity.native_step

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the number entity."""
        return self.entity_data.entity.name

    @property
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self.entity_data.entity.icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self.entity_data.entity.native_unit_of_measurement

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value from HA."""
        await self.entity_data.entity.async_set_native_value(value)
        self.async_write_ha_state()

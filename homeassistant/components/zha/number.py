"""Support for ZHA AnalogOutput cluster."""

from __future__ import annotations

import functools
import logging

from homeassistant.components.number import RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UndefinedType

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    get_zha_data,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation Analog Output from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.NUMBER]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, ZhaNumber, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZhaNumber(ZHAEntity, RestoreNumber):
    """Representation of a ZHA Number entity."""

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the number entity."""
        if (description := self.entity_data.entity.description) is None:
            return super().name

        # The name of this entity is reported by the device itself.
        # For backwards compatibility, we keep the same format as before. This
        # should probably be changed in the future to omit the prefix.
        return f"{super().name} {description}"

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
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self.entity_data.entity.native_unit_of_measurement

    @convert_zha_error_to_ha_error
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value from HA."""
        await self.entity_data.entity.async_set_native_value(value=value)
        self.async_write_ha_state()

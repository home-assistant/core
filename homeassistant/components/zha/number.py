"""Support for ZHA AnalogOutput cluster."""

import functools
import logging
from typing import Any, override

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
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

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA number entity."""
        super().__init__(entity_data, **kwargs)
        entity = entity_data.entity
        if entity.device_class is not None:
            self._attr_device_class = NumberDeviceClass(entity.device_class)

    @override
    def _update_capability_attrs(self) -> None:
        """Re-derive capability attributes from the cached state."""
        state = self._zha_state
        self._attr_mode = NumberMode(state.mode)
        self._attr_native_min_value = state.native_min_value
        self._attr_native_max_value = state.native_max_value
        self._attr_native_step = state.native_step
        self._attr_native_unit_of_measurement = state.native_unit_of_measurement

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._zha_state.native_value

    @convert_zha_error_to_ha_error()
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value from HA."""
        await self.entity_data.entity.async_set_native_value(value=value)
        self.async_write_ha_state()

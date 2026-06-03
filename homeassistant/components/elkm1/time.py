"""Support for ElkM1 time entities."""

from datetime import time as dt_time
import logging
from typing import Any, cast

from elkm1_lib.const import SettingFormat
from elkm1_lib.elements import Element
from elkm1_lib.settings import Setting

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElkM1ConfigEntry
from .entity import ElkAttachedEntity, ElkEntity, create_elk_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElkM1ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Elk-M1 time platform."""
    elk_data = config_entry.runtime_data
    elk = elk_data.elk
    entities: list[ElkEntity] = []
    time_settings = [
        setting
        for setting in cast(list[Setting], elk.settings)
        if setting.value_format is SettingFormat.TIME_OF_DAY
    ]

    create_elk_entities(
        elk_data,
        time_settings,
        "setting",
        ElkTimeSetting,
        entities,
    )
    async_add_entities(entities)


class ElkTimeSetting(ElkAttachedEntity, TimeEntity):
    """Representation of an Elk-M1 Time Setting."""

    _element: Setting

    def _element_changed(self, element: Element, changeset: dict[str, Any]) -> None:
        value = self._element.value
        # Guard against the panel possibly changing the underlying
        # type without us knowing about the change
        if isinstance(value, tuple):
            self._attr_native_value = dt_time(hour=value[0], minute=value[1])
        else:
            self._attr_available = False
            _LOGGER.warning(
                "Setting type for '%s' differs between the"
                " ElkM1 and the entity. Restart the"
                " integration to fix",
                self.entity_id,
            )

    async def async_set_value(self, value: dt_time) -> None:
        """Set the time of the setting."""
        self._element.set((value.hour, value.minute))

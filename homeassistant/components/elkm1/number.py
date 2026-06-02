"""Support for ElkM1 number entities."""

import logging
from typing import Any, cast

from elkm1_lib.const import SettingFormat
from elkm1_lib.elements import Element
from elkm1_lib.settings import Setting

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElkM1ConfigEntry
from .entity import ElkAttachedEntity, ElkEntity, create_elk_entities
from .models import ELKM1Data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElkM1ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Elk-M1 number platform."""
    elk_data = config_entry.runtime_data
    elk = elk_data.elk
    entities: list[ElkEntity] = []
    number_settings = [
        setting
        for setting in cast(list[Setting], elk.settings)
        if setting.value_format in (SettingFormat.NUMBER, SettingFormat.TIMER)
    ]

    create_elk_entities(
        elk_data,
        number_settings,
        "setting",
        ElkNumberSetting,
        entities,
    )
    async_add_entities(entities)


class ElkNumberSetting(ElkAttachedEntity, NumberEntity):
    """Representation of an Elk-M1 Number Setting."""

    _element: Setting

    _attr_native_min_value = 0
    _attr_native_max_value = 65535
    _attr_native_step = 1

    def __init__(self, element: Setting, elk: Any, elk_data: ELKM1Data) -> None:
        """Initialize the number setting."""
        super().__init__(element, elk, elk_data)
        if element.value_format is SettingFormat.TIMER:
            self._attr_device_class = NumberDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def _element_changed(self, element: Element, changeset: dict[str, Any]) -> None:
        # Guard against the panel possibly changing the underlying
        # type without us knowing about the change
        if isinstance(self._element.value, int):
            self._attr_native_value = self._element.value
        else:
            self._attr_available = False
            _LOGGER.warning(
                "Setting type for '%s' differs between the"
                " ElkM1 and the entity. Restart the"
                " integration to fix",
                self.entity_id,
            )

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the setting."""
        self._element.set(int(value))

"""The Tag sensor."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any, final

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN, Event, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import LAST_SCANNED, TAGS, TagStorageCollection
from .const import DEVICE_ID, EVENT_TAG_SCANNED, TAG_ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tag Sensor."""
    if not discovery_info:
        return
    storage_collection: TagStorageCollection = hass.data[DOMAIN][TAGS]
    name = discovery_info[CONF_NAME]
    tag_id = discovery_info[TAG_ID]
    initial_state = storage_collection.data[tag_id]
    async_add_entities([TagSensor(name, tag_id, initial_state)])


class TagSensor(SensorEntity):
    """Representation of a Tag sensor."""

    _unrecorded_attributes = frozenset({TAG_ID})

    def __init__(self, name: str, tag_id: str, initial_state: dict) -> None:
        """Initialize the Tag sensor."""
        self._attr_name = name
        self._tag_id = tag_id
        if last_scanned := initial_state.get(LAST_SCANNED):
            self._attr_native_value = datetime.fromisoformat(last_scanned)
        self._last_event_device_id: str | None = initial_state.get(DEVICE_ID)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.hass.bus.async_listen(EVENT_TAG_SCANNED, self._trigger_tag)
        await super().async_added_to_hass()

    @final
    def _trigger_tag(self, event: Event) -> None:
        """Process a new event."""
        self._attr_native_value = event.time_fired
        self._last_event_device_id = event.data[DEVICE_ID]

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self._attr_native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            TAG_ID: self._tag_id,
            DEVICE_ID: self._last_event_device_id,
        }

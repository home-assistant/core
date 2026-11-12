"""Events on Zigbee Home Automation networks."""

import functools
from typing import override

from zha.application.platforms.event import EntityEventTriggeredEvent

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation event from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.EVENT]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, ZHAEvent, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHAEvent(ZHAEntity, EventEntity):
    """ZHA event."""

    @override
    def _update_capability_attrs(self) -> None:
        """Re-derive capability attributes from the cached state."""
        super()._update_capability_attrs()

        device_class = self._zha_state.device_class
        self._attr_device_class = (
            EventDeviceClass(device_class) if device_class is not None else None
        )
        self._attr_event_types = self._zha_state.event_types

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsubs.append(
            self.entity_data.entity.on_event(
                EntityEventTriggeredEvent.event, self._handle_entity_events
            )
        )

    @callback
    def _handle_entity_events(self, data: EntityEventTriggeredEvent) -> None:
        """Handle an event triggered by the ZHA entity."""
        self.debug("Handling event from entity: %s", data.triggered.event_type)
        self._trigger_event(data.triggered.event_type, data.triggered.event_attributes)
        self.async_write_ha_state()

"""Support for RFXtrx sensors."""

from __future__ import annotations

import logging
from typing import Any

from RFXtrx import ControlEvent, RFXtrxDevice, RFXtrxEvent, SensorEvent

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import DeviceTuple, async_setup_platform_entry
from .const import DEVICE_PACKET_TYPE_LIGHTING4
from .entity import RfxtrxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up config entry."""

    def _supported(event: RFXtrxEvent) -> bool:
        return (
            isinstance(event, (ControlEvent, SensorEvent))
            and event.device.packettype != DEVICE_PACKET_TYPE_LIGHTING4
        )

    def _constructor(
        event: RFXtrxEvent,
        auto: RFXtrxEvent | None,
        device_id: DeviceTuple,
        entity_info: dict[str, Any],
    ) -> list[Entity]:
        entities: list[Entity] = []

        if hasattr(event.device, "COMMANDS"):
            entities.append(
                RfxtrxEventEntity(
                    event.device, device_id, "COMMANDS", "Command", "command"
                )
            )

        if hasattr(event.device, "STATUS"):
            entities.append(
                RfxtrxEventEntity(
                    event.device, device_id, "STATUS", "Sensor Status", "status"
                )
            )

        return entities

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, _supported, _constructor
    )


class RfxtrxEventEntity(RfxtrxEntity, EventEntity):
    """Representation of a RFXtrx event."""

    def __init__(
        self,
        device: RFXtrxDevice,
        device_id: DeviceTuple,
        device_attribute: str,
        value_attribute: str,
        translation_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_id)
        commands: dict[int, str] = getattr(device, device_attribute)
        self._attr_name = None
        self._attr_unique_id = "_".join(x for x in device_id)
        self._attr_event_types = [slugify(command) for command in commands.values()]
        self._attr_translation_key = translation_key
        self._value_attribute = value_attribute

    @callback
    def _handle_event(self, event: RFXtrxEvent, device_id: DeviceTuple) -> None:
        """Check if event applies to me and update."""
        if not self._event_applies(event, device_id):
            return

        assert isinstance(event, (ControlEvent, SensorEvent))

        event_type = slugify(event.values[self._value_attribute])
        if event_type not in self._attr_event_types:
            _LOGGER.warning("Event type %s is not known", event_type)
            return

        self._trigger_event(event_type, event.values)
        self.async_write_ha_state()

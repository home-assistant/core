"""Tests for the Universal Devices ISY/IoX integration."""

from pyisy.helpers import EventEmitter, EventListener

from homeassistant.helpers.entity import Entity


def entity_listeners(emitter: EventEmitter, entity: Entity) -> list[EventListener]:
    """Return the listeners of an emitter whose callback is bound to the entity."""
    return [
        listener
        for listener in emitter._subscribers
        if getattr(listener.callback, "__self__", None) is entity
    ]

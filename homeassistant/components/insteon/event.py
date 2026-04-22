"""Support for INSTEON device events."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import Any

from pyinsteon.address import Address
from pyinsteon.device_types.device_base import Device
from pyinsteon.events import OFF_EVENT, OFF_FAST_EVENT, ON_EVENT, ON_FAST_EVENT, Event

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SIGNAL_ADD_ENTITIES
from .entity import InsteonBaseEntity
from .utils import async_add_insteon_devices, async_add_insteon_entities

_BUTTON_EVENT_NAMES = (OFF_EVENT, OFF_FAST_EVENT, ON_EVENT, ON_FAST_EVENT)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Insteon events from a config entry."""

    @callback
    def async_add_insteon_event_entities(discovery_info: dict[str, Any]):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            Platform.EVENT,
            InsteonEventEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.EVENT}"
    async_dispatcher_connect(hass, signal, async_add_insteon_event_entities)
    async_add_insteon_devices(
        hass,
        Platform.EVENT,
        InsteonEventEntity,
        async_add_entities,
    )


def _register_entity_event(event: Event, listener: Callable[..., None]) -> None:
    """Register an Insteon event raised by a device."""

    _LOGGER.debug(
        "Registering event for %s group %d %s",
        str(event.address),
        event.group,
        event.name,
    )

    event.subscribe(listener, force_strong_ref=True)


class InsteonEventEntity(InsteonBaseEntity, EventEntity):
    """Representation of a Insteon Event entity."""

    def __init__(self, device: Device, group: int) -> None:
        """Initialize the event entity."""
        super().__init__(device=device, group=group)

        self._attr_has_entity_name = True

        self._attr_translation_key = (
            "main" if self._insteon_device_group.group == 1 else "additional"
        ) + "_button_press"

        self._attr_translation_placeholders = {
            "button": self._insteon_device_group.name.rpartition('_')[-1].upper()
        }


        @callback
        def async_fire_button_event(
            name: str, address: Address, group: int, button: str | None = None
        ):
            if name in _BUTTON_EVENT_NAMES:
                _LOGGER.debug(
                    "Firing event entity for %s group %d %s button %s",
                    str(address),
                    group,
                    name,
                    button,
                )
                self._trigger_event(name.removesuffix("_event"), {})
                self.async_write_ha_state()

        event_types: list[str] = []

        # keep track of registered event listeners so we can unsubscribe later
        self._insteon_event_listeners: list[tuple[Event, Callable[..., None]]] = []

        events = device.events[group].values()
        event_names = [item.name for item in events]

        # if the device is only a subset of 4 button events
        # set the device class to button and add the event types to the entity description.
        if set(event_names).issubset(_BUTTON_EVENT_NAMES):
            self.device_class = EventDeviceClass.BUTTON

            for event in events:
                event_types.append(event.name.removesuffix("_event"))
                _register_entity_event(event, async_fire_button_event)
                self._insteon_event_listeners.append((event, async_fire_button_event))

        self._attr_event_types = event_types

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe any registered Insteon event listeners."""
        for event, listener in getattr(self, "_insteon_event_listeners", []):
            try:
                event.unsubscribe(listener)
            except (TypeError, ValueError) as err:  # only handle expected call errors
                _LOGGER.debug(
                    "Failed to unsubscribe listener for %s group %s: %s",
                    str(getattr(event, "address", "unknown")),
                    getattr(event, "group", "?"),
                    err,
                )
        await super().async_will_remove_from_hass()

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID for the event entity."""
        return super().unique_id + "_event"

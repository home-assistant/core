"""Support for bthome event entities."""
from __future__ import annotations

import logging

from sensor_state_data import DeviceKey

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import format_discovered_device_key, format_event_dispatcher_name
from .const import (
    DOMAIN,
    EVENT_CLASS_BUTTON,
    EVENT_CLASS_DIMMER,
    EVENT_PROPERTIES,
    EVENT_TYPE,
    BTHomeBleEvent,
)
from .coordinator import BTHomePassiveBluetoothProcessorCoordinator

_LOGGER = logging.getLogger(__name__)

DESCRIPTIONS_BY_EVENT_CLASS = {
    EVENT_CLASS_BUTTON: EventEntityDescription(
        key=EVENT_CLASS_BUTTON,
        translation_key="button",
        event_types=[
            "press",
            "double_press",
            "triple_press",
            "long_press",
            "long_double_press",
            "long_triple_press",
        ],
        device_class=EventDeviceClass.BUTTON,
    ),
    EVENT_CLASS_DIMMER: EventEntityDescription(
        key=EVENT_CLASS_DIMMER,
        translation_key="dimmer",
        event_types=["rotate_left", "rotate_right"],
    ),
}


class BTHomeEventEntity(EventEntity):
    """Representation of a BTHome event entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, address: str, event_class: str, device_id: str | None) -> None:
        """Initialise a BTHome event entity."""
        self._update_signal = format_event_dispatcher_name(address, event_class)
        self.entity_description = DESCRIPTIONS_BY_EVENT_CLASS[event_class]
        # Matches logic in PassiveBluetoothProcessorEntity
        if device_id:
            self._attr_device_info = dr.DeviceInfo(
                identifiers={(DOMAIN, f"{address}-{device_id}")}
            )
            self._attr_unique_id = f"{address}-{event_class}-{device_id}"
        else:
            self._attr_device_info = dr.DeviceInfo(
                identifiers={(DOMAIN, address)},
                connections={(dr.CONNECTION_BLUETOOTH, address)},
            )
            self._attr_unique_id = f"{address}-{event_class}"

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._update_signal,
                self._handle_event,
            )
        )

    @callback
    def _handle_event(self, event: BTHomeBleEvent) -> None:
        self._trigger_event(event[EVENT_TYPE], event[EVENT_PROPERTIES])
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BTHome event."""
    coordinator: BTHomePassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    address = coordinator.address
    discovered_event_entities: set[tuple[str, str | None]] = set()
    ent_reg = er.async_get(hass)
    to_add: list[BTHomeEventEntity] = []
    for ent_reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if ent_reg_entry.domain != "event":
            continue
        unique_id_split = ent_reg_entry.unique_id.split("-")
        device_id: str | None = None
        if len(unique_id_split) == 3:
            address, event_class, device_id = unique_id_split
        else:
            address, event_class = unique_id_split
            device_id = None
        discovery_key = (event_class, device_id)
        discovered_event_entities.add(discovery_key)
        to_add.append(BTHomeEventEntity(address, event_class, device_id))

    async_add_entities(to_add)

    @callback
    def _async_discovered_event_class(device_key: DeviceKey) -> None:
        """Handle a discovered event class."""
        event_class = device_key.key
        device_id = device_key.device_id
        discovery_key = (event_class, device_id)
        if discovery_key in discovered_event_entities:
            return
        discovered_event_entities.add(discovery_key)
        async_add_entities([BTHomeEventEntity(address, event_class, device_id)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            format_discovered_device_key(address),
            _async_discovered_event_class,
        )
    )

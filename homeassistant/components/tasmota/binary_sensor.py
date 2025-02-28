"""Support for Tasmota binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from hatasmota import switch as tasmota_switch
from hatasmota.entity import TasmotaEntity as HATasmotaEntity
from hatasmota.models import DiscoveryHashType

from homeassistant.components import binary_sensor
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import event as evt
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .entity import TasmotaAvailability, TasmotaDiscoveryUpdate


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tasmota binary sensor dynamically through discovery."""

    @callback
    def async_discover(
        tasmota_entity: HATasmotaEntity, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota binary sensor."""
        async_add_entities(
            [
                TasmotaBinarySensor(
                    tasmota_entity=tasmota_entity, discovery_hash=discovery_hash
                )
            ]
        )

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(binary_sensor.DOMAIN)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_ENTITY_NEW.format(binary_sensor.DOMAIN),
            async_discover,
        )
    )


class TasmotaBinarySensor(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    BinarySensorEntity,
):
    """Representation a Tasmota binary sensor."""

    _delay_listener: Callable | None = None
    _on_off_state: bool | None = None
    _tasmota_entity: tasmota_switch.TasmotaSwitch

    def __init__(self, **kwds: Any) -> None:
        """Initialize the Tasmota binary sensor."""
        super().__init__(
            **kwds,
        )
        if self._tasmota_entity.off_delay is not None:
            self._attr_force_update = True

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_state_callback(self.on_off_state_updated)
        await super().async_added_to_hass()

    @callback
    def off_delay_listener(self, now: datetime) -> None:
        """Switch device off after a delay."""
        self._delay_listener = None
        self._on_off_state = False
        self.async_write_ha_state()

    @callback
    def on_off_state_updated(self, state: bool, **kwargs: Any) -> None:
        """Handle state updates."""
        self._on_off_state = state

        if self._delay_listener is not None:
            self._delay_listener()
            self._delay_listener = None

        off_delay = self._tasmota_entity.off_delay
        if self._on_off_state and off_delay is not None:
            self._delay_listener = evt.async_call_later(
                self.hass, off_delay, self.off_delay_listener
            )

        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._on_off_state

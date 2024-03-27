"""Switch for PG LAB Electronics."""
from __future__ import annotations

from typing import Any

from pypglab.device import Device
from pypglab.relay import Relay

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CREATE_NEW_ENTITY, DISCONNECT_COMPONENT
from .entity import BaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""

    @callback
    def async_discover(pglab_device: Device, pglab_relay: Relay) -> None:
        """Discover and add a PG LAB Relay."""
        pglab_switch = PgLab_Switch(pglab_device, pglab_relay)
        async_add_entities([pglab_switch])

    hass.data[DISCONNECT_COMPONENT[Platform.SWITCH]] = async_dispatcher_connect(
        hass, CREATE_NEW_ENTITY[Platform.SWITCH], async_discover
    )


class PgLab_Switch(BaseEntity, SwitchEntity):
    """A PG LAB switch."""

    def __init__(self, pglab_device: Device, pglab_relay: Relay) -> None:
        """Initialize the Switch class."""

        super().__init__(
            platform=Platform.SWITCH, device=pglab_device, entity=pglab_relay
        )

        self._attr_unique_id = f"{pglab_device.id}_relay{pglab_relay.id}_switch"
        self._attr_name = f"{pglab_device.name}_relay{pglab_relay.id}"

        self._relay = pglab_relay

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._relay.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._relay.turn_off()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._relay.state

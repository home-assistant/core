"""Switch for PG LAB Electronics."""

from __future__ import annotations

from typing import Any

from pypglab.device import Device as PyPGLabDevice
from pypglab.relay import Relay as PyPGLabRelay

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .discovery import PGLABConfigEntry, PGLabDiscovery
from .entity import PgLabEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PGLABConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""

    @callback
    def async_discover(pglab_device: PyPGLabDevice, pglab_relay: PyPGLabRelay) -> None:
        """Discover and add a PG LAB Relay."""
        pglab_discovery = config_entry.runtime_data
        pglab_switch = PgLabSwitch(pglab_discovery, pglab_device, pglab_relay)
        async_add_entities([pglab_switch])

    # register the callback to create the switch entity when discovered
    pglab_discovery = config_entry.runtime_data
    await pglab_discovery.register_platform(hass, Platform.SWITCH, async_discover)


class PgLabSwitch(PgLabEntity, SwitchEntity):
    """A PG LAB switch."""

    def __init__(
        self,
        pglab_discovery: PGLabDiscovery,
        pglab_device: PyPGLabDevice,
        pglab_relay: PyPGLabRelay,
    ) -> None:
        """Initialize the Switch class."""

        super().__init__(
            discovery=pglab_discovery,
            platform=Platform.SWITCH,
            device=pglab_device,
            entity=pglab_relay,
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

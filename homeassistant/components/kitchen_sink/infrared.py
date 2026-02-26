"""Demo platform that offers a fake infrared entity."""

from __future__ import annotations

import infrared_protocols

from homeassistant.components import persistent_notification
from homeassistant.components.infrared import InfraredEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo infrared platform."""
    async_add_entities(
        [
            DemoInfrared(
                unique_id="ir_transmitter",
                device_name="IR Blaster",
                entity_name="Infrared Transmitter",
            ),
        ]
    )


class DemoInfrared(InfraredEntity):
    """Representation of a demo infrared entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        entity_name: str,
    ) -> None:
        """Initialize the demo infrared entity."""
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_name = entity_name

    async def async_send_command(self, command: infrared_protocols.Command) -> None:
        """Send an IR command."""
        timings = [
            interval
            for timing in command.get_raw_timings()
            for interval in (timing.high_us, -timing.low_us)
        ]
        persistent_notification.async_create(
            self.hass, str(timings), title="Infrared Command"
        )

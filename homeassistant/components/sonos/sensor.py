"""Entity representing a Sonos battery level."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SONOS_CREATE_BATTERY
from .entity import SonosEntity
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    async def _async_create_entity(speaker: SonosSpeaker) -> None:
        entity = SonosBatteryEntity(speaker)
        async_add_entities([entity])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_BATTERY, _async_create_entity)
    )


class SonosBatteryEntity(SonosEntity, SensorEntity):
    """Representation of a Sonos Battery entity."""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self.soco.uid}-battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.speaker.zone_name} Battery"

    @property
    def device_class(self) -> str:
        """Return the entity's device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement."""
        return PERCENTAGE

    async def async_update(self) -> None:
        """Poll the device for the current state."""
        await self.speaker.async_poll_battery()

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        return self.speaker.battery_info.get("Level")

    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self.speaker.available and self.speaker.power_source

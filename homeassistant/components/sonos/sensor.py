"""Entity representing a Sonos battery level."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import DATA_SONOS, SONOS_DISCOVERY_UPDATE, SONOS_ENTITY_CREATED
from .entity import SonosEntity
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    async def _async_create_entity(speaker: SonosSpeaker) -> SonosBatteryEntity | None:
        if speaker.battery_info:
            return SonosBatteryEntity(speaker, hass.data[DATA_SONOS])
        return None

    async def _async_create_entities(speaker: SonosSpeaker):
        if entity := await _async_create_entity(speaker):
            async_add_entities([entity])
        else:
            async_dispatcher_send(
                hass, f"{SONOS_ENTITY_CREATED}-{speaker.soco.uid}", SENSOR_DOMAIN
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_DISCOVERY_UPDATE, _async_create_entities)
    )


class SonosBatteryEntity(SonosEntity, SensorEntity):
    """Representation of a Sonos Battery entity."""

    async def async_added_to_hass(self) -> None:
        """Register polling callback when added to hass."""
        await super().async_added_to_hass()
        async_dispatcher_send(
            self.hass, f"{SONOS_ENTITY_CREATED}-{self.soco.uid}", SENSOR_DOMAIN
        )

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

    async def async_update(self, now: datetime.datetime | None = None) -> None:
        """Poll the device for the current state."""
        await self.speaker.async_poll_battery()

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        return self.speaker.battery_info.get("Level")

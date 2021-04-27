"""Entity representing a Sonos power sensor."""
from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import DATA_SONOS, SONOS_DISCOVERY_UPDATE, SONOS_ENTITY_CREATED
from .entity import SonosSensorEntity
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY_POWER_SOURCE = "power_source"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    async def _async_create_entity(speaker: SonosSpeaker) -> SonosPowerEntity | None:
        if speaker.battery_info:
            return SonosPowerEntity(speaker, hass.data[DATA_SONOS])
        return None

    async def _async_create_entities(speaker: SonosSpeaker):
        if entity := await _async_create_entity(speaker):
            async_add_entities([entity])
        else:
            async_dispatcher_send(
                hass, f"{SONOS_ENTITY_CREATED}-{speaker.soco.uid}", BINARY_SENSOR_DOMAIN
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_DISCOVERY_UPDATE, _async_create_entities)
    )


class SonosPowerEntity(SonosSensorEntity, BinarySensorEntity):
    """Representation of a Sonos power entity."""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self.soco.uid}-power"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.speaker.zone_name} Power"

    @property
    def device_class(self) -> str:
        """Return the entity's device class."""
        return DEVICE_CLASS_BATTERY_CHARGING

    async def async_update(self, now: datetime.datetime | None = None) -> None:
        """Poll the device for the current state."""
        await self.speaker.async_poll_battery()

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.speaker.charging

    @property
    def device_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            ATTR_BATTERY_POWER_SOURCE: self.speaker.power_source,
        }

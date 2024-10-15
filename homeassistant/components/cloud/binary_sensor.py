"""Support for Home Assistant Cloud binary sensors."""

from __future__ import annotations

import asyncio
from typing import Any

from hass_nabucasa import Cloud

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import CloudClient
from .const import DATA_CLOUD, DISPATCHER_REMOTE_UPDATE

WAIT_UNTIL_CHANGE = 3


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Assistant Cloud binary sensors."""
    cloud = hass.data[DATA_CLOUD]
    async_add_entities([CloudRemoteBinary(cloud)])


class CloudRemoteBinary(BinarySensorEntity):
    """Representation of an Cloud Remote UI Connection binary sensor."""

    _attr_name = "Remote UI"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False
    _attr_unique_id = "cloud-remote-ui-connectivity"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, cloud: Cloud[CloudClient]) -> None:
        """Initialize the binary sensor."""
        self.cloud = cloud

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.cloud.remote.is_connected

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.cloud.remote.certificate is not None

    async def async_added_to_hass(self) -> None:
        """Register update dispatcher."""

        async def async_state_update(data: Any) -> None:
            """Update callback."""
            await asyncio.sleep(WAIT_UNTIL_CHANGE)
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCHER_REMOTE_UPDATE, async_state_update
            )
        )

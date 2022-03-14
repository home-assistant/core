"""Support for Home Assistant Cloud binary sensors."""
from __future__ import annotations

import asyncio

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DISPATCHER_REMOTE_UPDATE, DOMAIN

WAIT_UNTIL_CHANGE = 3


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the cloud binary sensors."""
    if discovery_info is None:
        return
    cloud = hass.data[DOMAIN]

    async_add_entities([CloudRemoteBinary(cloud)])


class CloudRemoteBinary(BinarySensorEntity):
    """Representation of an Cloud Remote UI Connection binary sensor."""

    _attr_name = "Remote UI"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False
    _attr_unique_id = "cloud-remote-ui-connectivity"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, cloud):
        """Initialize the binary sensor."""
        self.cloud = cloud
        self._unsub_dispatcher = None

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.cloud.remote.is_connected

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.cloud.remote.certificate is not None

    async def async_added_to_hass(self):
        """Register update dispatcher."""

        async def async_state_update(data):
            """Update callback."""
            await asyncio.sleep(WAIT_UNTIL_CHANGE)
            self.async_write_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, DISPATCHER_REMOTE_UPDATE, async_state_update
        )

    async def async_will_remove_from_hass(self):
        """Register update dispatcher."""
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

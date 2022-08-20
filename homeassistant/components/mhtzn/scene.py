"""Business logic for scene entity."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MQTT_CLIENT_INSTANCE, EVENT_ENTITY_REGISTER

_LOGGER = logging.getLogger(__name__)

COMPONENT = "scene"


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """This method is executed after the integration is initialized to create an event listener,
     which is used to create a sub-device"""

    async def async_discover(config_payload):
        try:
            async_add_entities([CustomScene(hass, config_payload, config_entry)])
        except Exception:
            raise

    async_dispatcher_connect(
        hass, EVENT_ENTITY_REGISTER.format(COMPONENT), async_discover
    )


class CustomScene(Scene):
    """Custom entity class to handle business logic related to scenes"""

    def activate(self, **kwargs: Any) -> None:
        pass

    should_poll = False

    def __init__(self, hass: HomeAssistant, config: dict, config_entry: ConfigEntry) -> None:
        self._attr_unique_id = config["unique_id"]

        self._attr_entity_id = config["unique_id"]

        self.id = config["id"]

        self._attr_name = config["name"]

        self.hass = hass

        self.config_entry = config_entry

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            # If desired, the name for the device could be different to the entity
            "name": self.name,
            "manufacturer": "Netmoon",
        }

    async def async_activate(self, **kwargs):
        """execution scenario"""

        await self.exec_command()

    async def exec_command(self):
        message = {
            "seq": 1,
            "data": {
                "id": self.id
            }
        }

        await self.hass.data[MQTT_CLIENT_INSTANCE].async_publish(
            "P/0/center/q30",
            json.dumps(message),
            0,
            False
        )

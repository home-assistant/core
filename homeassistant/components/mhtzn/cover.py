"""Business logic for cover entity."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity, SUPPORT_STOP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MQTT_CLIENT_INSTANCE, EVENT_ENTITY_STATE_UPDATE, CACHE_ENTITY_STATE_UPDATE_KEY_DICT, \
    EVENT_ENTITY_REGISTER

_LOGGER = logging.getLogger(__name__)

COMPONENT = "cover"


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """This method is executed after the integration is initialized to create an event listener,
    which is used to create a sub-device"""

    async def async_discover(config_payload):
        try:
            async_add_entities([CustomCover(hass, config_payload, config_entry)])
        except Exception:
            raise

    async_dispatcher_connect(
        hass, EVENT_ENTITY_REGISTER.format(COMPONENT), async_discover
    )


class CustomCover(CoverEntity):
    """Custom entity class to handle business logic related to curtains"""

    def close_cover(self, **kwargs: Any) -> None:
        pass

    def open_cover(self, **kwargs: Any) -> None:
        pass

    should_poll = False

    """Supports set position, open, close and stop operations"""
    supported_features = SUPPORT_SET_POSITION | SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    """Device class is curtain"""
    device_class = "curtain"

    def __init__(self, hass: HomeAssistant, config: dict, config_entry: ConfigEntry) -> None:
        self._attr_unique_id = config["unique_id"]

        self._attr_entity_id = config["unique_id"]

        self.sn = config["sn"]

        self._attr_name = config["name"]

        self._attr_device_class = "curtain"

        self._target_position = 100

        self._current_position = 100

        self.hass = hass

        self.config_entry = config_entry

        self.moving = 0

        self.update_state(config)

        async def async_discover(data: dict):
            try:
                self.update_state(data)
                self.async_write_ha_state()
            except Exception:
                raise

        """Add a device state change event listener, and execute the specified method when the device state changes. 
        Note: It is necessary to determine whether an event listener has been added here to avoid repeated additions."""
        key = EVENT_ENTITY_STATE_UPDATE.format(self.unique_id)
        if key not in hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT]:
            hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT][key] = async_dispatcher_connect(
                hass, key, async_discover
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            # If desired, the name for the device could be different to the entity
            "name": self.name,
            "manufacturer": "Netmoon",
        }

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self.position == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.moving < 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.moving > 0

    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return True

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.position

    @property
    def position(self):
        """Return position for roller."""
        return self._current_position

    def update_state(self, data):
        position = int(data["travel"] * 100)
        self._target_position = position
        self._current_position = self._target_position

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.exec_command(0, 0)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.set_position(100)
        await self.exec_command(1, 0)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.set_position(0)
        await self.exec_command(2, 0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Close the cover."""
        position = kwargs[ATTR_POSITION]
        await self.set_position(kwargs[ATTR_POSITION])
        await self.exec_command(3, position)

    async def set_position(self, position: int) -> None:
        """Change curtain position in HA"""
        self._target_position = position

        self._current_position = self._target_position

        self.async_write_ha_state()

    async def exec_command(self, action: int, position: int):
        """Execute MQTT commands"""
        message = {
            "seq": 1,
            "data": {
                "sn": self.sn,
                "action": action
            }
        }

        if action == 3:
            message["data"]["travel"] = round(position / 100, 2)

        await self.hass.data[MQTT_CLIENT_INSTANCE].async_publish(
            "P/0/center/q21",
            json.dumps(message),
            0,
            False
        )

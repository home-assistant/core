"""Entity for Zigbee Home Automation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from zha.mixins import LogMixin

from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE, DeviceInfo

from .const import DOMAIN
from .helpers import EntityData

_LOGGER = logging.getLogger(__name__)

ENTITY_SUFFIX = "entity_suffix"
DEFAULT_UPDATE_GROUP_FROM_CHILD_DELAY = 0.5


class ZHAEntity(LogMixin, entity.Entity):
    """ZHA eitity."""

    remove_future: asyncio.Future[Any]
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entity_data: EntityData) -> None:
        """Init ZHA entity."""
        super().__init__()
        self.entity_data: EntityData = entity_data
        self._unsubs: list[Callable[[], None]] = []
        self._unsubs.append(
            entity_data.entity.on_all_events(self._handle_entity_events)
        )
        if (
            hasattr(self.entity_data.entity, "_attr_translation_key")
            and self.entity_data.entity._attr_translation_key is not None
        ):
            self._attr_translation_key = self.entity_data.entity._attr_translation_key
        if (
            hasattr(self.entity_data.entity, "_attr_entity_category")
            and self.entity_data.entity._attr_entity_category is not None
        ):
            self._attr_entity_category = self.entity_data.entity._attr_entity_category

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.entity_data.entity.unique_id

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.entity_data.device_proxy.device.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        zha_device_info = self.entity_data.device_proxy.device.device_info
        ieee = zha_device_info["ieee"]
        zha_gateway = self.entity_data.device_proxy.gateway_proxy.gateway

        return DeviceInfo(
            connections={(CONNECTION_ZIGBEE, ieee)},
            identifiers={(DOMAIN, ieee)},
            manufacturer=zha_device_info[ATTR_MANUFACTURER],
            model=zha_device_info[ATTR_MODEL],
            name=zha_device_info[ATTR_NAME],
            via_device=(DOMAIN, zha_gateway.state.node_info.ieee),
        )

    @callback
    def _handle_entity_events(self, event: Any) -> None:
        """Entity state changed."""
        self.debug("Handling event from entity: %s", event)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        for unsub in self._unsubs[:]:
            unsub()
            self._unsubs.remove(unsub)
        await super().async_will_remove_from_hass()
        self.remove_future.set_result(True)

    def log(self, level: int, msg: str, *args, **kwargs):
        """Log a message."""
        msg = f"%s: {msg}"
        args = (self.entity_id, *args)
        _LOGGER.log(level, msg, *args, **kwargs)

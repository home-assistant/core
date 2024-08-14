"""Support for switch entities."""

from __future__ import annotations

from collections.abc import Collection
import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .const import THINQ_DEVICE_ADDED
from .device import LGDevice
from .entity_helpers import ThinQEntity, ThinQSwitchEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for switch platform."""
    _LOGGER.warning("Starting set up switch platform")

    @callback
    def async_add_devices(devices: Collection[LGDevice]) -> None:
        """Add switch entities."""
        async_add_entities(ThinQSwitchEntity.create_entities(devices))

    async_add_devices(entry.runtime_data.device_map.values())

    entry.async_on_unload(
        async_dispatcher_connect(hass, THINQ_DEVICE_ADDED, async_add_devices)
    )


class ThinQSwitchEntity(ThinQEntity[ThinQSwitchEntityDescription], SwitchEntity):
    """Represent a thinq switch platform."""

    entity_description: ThinQSwitchEntityDescription
    target_platform = Platform.SWITCH
    attr_device_class = SwitchDeviceClass.SWITCH

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        self._attr_is_on = self.get_value_as_bool()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self._attr_is_on = True
        self.async_write_ha_state()

        _LOGGER.debug("[%s] async_turn_on", self.name)
        await self.async_post_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self._attr_is_on = False
        self.async_write_ha_state()

        _LOGGER.debug("[%s] async_turn_off", self.name)
        await self.async_post_value(False)

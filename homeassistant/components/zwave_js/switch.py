"""Representation of Z-Wave switches."""

import logging
from typing import Any, Callable, List

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_switch(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Switch."""
        entities: List[ZWaveBaseEntity] = []
        entities.append(ZWaveSwitch(config_entry, client, info))

        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SWITCH_DOMAIN}",
            async_add_switch,
        )
    )


class ZWaveSwitch(ZWaveBaseEntity, SwitchEntity):
    """Representation of a Z-Wave switch."""

    @property
    def is_on(self) -> bool:
        """Return a boolean for the state of the switch."""
        return bool(self.info.primary_value.value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        target_value = self.get_zwave_value("targetValue")
        if target_value is not None:
            await self.info.node.async_set_value(target_value, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        target_value = self.get_zwave_value("targetValue")
        if target_value is not None:
            await self.info.node.async_set_value(target_value, False)

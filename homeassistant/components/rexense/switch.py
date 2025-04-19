"""Platform for Rexense switch integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RexenseConfigEntry
from .const import DOMAIN
from .websocket_client import RexenseWebsocketClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RexenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Rexense switch from a config entry."""
    client: RexenseWebsocketClient = entry.runtime_data

    for feature in client.feature_map:
        if "PowerSwitch" not in feature.get("Attributes", []):
            break

        async_add_entities([RexenseSwitch(client)], True)


class RexenseSwitch(SwitchEntity):
    """Representation of a Rexense plug switch."""

    _attr_has_entity_name = True

    def __init__(self, client: RexenseWebsocketClient) -> None:
        """Initialize the switch."""
        self._client = client
        self._attr_unique_id = f"{client.device_id}_switch"
        self._attr_name = "Power Switch"

    async def async_added_to_hass(self) -> None:
        """Register update listener when added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._client.signal_update, self.async_write_ha_state
            )
        )

    @property
    def is_on(self) -> bool:
        """Return True if the switch is currently on."""
        return bool(self._client.switch_state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._client.async_set_switch(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._client.async_set_switch(False)

    @property
    def available(self) -> bool:
        """Return True if the device is connected and state is known."""
        return self._client.connected and self._client.switch_state is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._client.device_id)},
            name=f"{self._client.model} ({self._client.device_id})",
            manufacturer="Rexense",
            model=self._client.model,
        )

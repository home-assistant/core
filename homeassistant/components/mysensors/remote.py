"""Support MySensors IR transceivers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from homeassistant.components.remote import (
    ATTR_COMMAND,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import setup_mysensors_platform
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .device import MySensorsChildEntity
from .helpers import on_unload


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    @callback
    def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors remote."""
        setup_mysensors_platform(
            hass,
            Platform.REMOTE,
            discovery_info,
            MySensorsRemote,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.REMOTE),
            async_discover,
        ),
    )


class MySensorsRemote(MySensorsChildEntity, RemoteEntity):
    """Representation of a MySensors IR transceiver."""

    _current_command: str | None = None

    @property
    def is_on(self) -> bool | None:
        """Return True if remote is on."""
        set_req = self.gateway.const.SetReq
        value = cast(str | None, self._child.values.get(set_req.V_LIGHT))
        if value is None:
            return None
        return value == "1"

    @property
    def supported_features(self) -> RemoteEntityFeature:
        """Flag supported features."""
        features = RemoteEntityFeature(0)
        set_req = self.gateway.const.SetReq
        if set_req.V_IR_RECORD in self._values:
            features = features | RemoteEntityFeature.LEARN_COMMAND
        return features

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device."""
        for cmd in command:
            self._current_command = cmd
            self.gateway.set_child_value(
                self.node_id, self.child_id, self.value_type, cmd, ack=1
            )

    async def async_learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        set_req = self.gateway.const.SetReq
        commands: list[str] | None = kwargs.get(ATTR_COMMAND)
        if commands is None:
            raise ValueError("Command not specified for learn_command service")

        for command in commands:
            self.gateway.set_child_value(
                self.node_id, self.child_id, set_req.V_IR_RECORD, command, ack=1
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the IR transceiver on."""
        set_req = self.gateway.const.SetReq
        if self._current_command:
            self.gateway.set_child_value(
                self.node_id,
                self.child_id,
                self.value_type,
                self._current_command,
                ack=1,
            )
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 1, ack=1
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the IR transceiver off."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 0, ack=1
        )

    @callback
    def _async_update(self) -> None:
        """Update the controller with the latest value from a device."""
        super()._async_update()
        self._current_command = cast(
            str | None, self._child.values.get(self.value_type)
        )

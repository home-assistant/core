"""Entity for Zigbee Home Automation."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import functools
import logging
from typing import TYPE_CHECKING, Any, TypeVar

from homeassistant.const import ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, Event, callback
from homeassistant.helpers import entity
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .core.const import (
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    DATA_ZHA,
    DATA_ZHA_BRIDGE_ID,
    DOMAIN,
    SIGNAL_GROUP_ENTITY_REMOVED,
    SIGNAL_GROUP_MEMBERSHIP_CHANGE,
    SIGNAL_REMOVE,
)
from .core.helpers import LogMixin

if TYPE_CHECKING:
    from .core.channels.base import ZigbeeChannel
    from .core.device import ZHADevice

_ZhaEntitySelfT = TypeVar("_ZhaEntitySelfT", bound="ZhaEntity")
_ZhaGroupEntitySelfT = TypeVar("_ZhaGroupEntitySelfT", bound="ZhaGroupEntity")

_LOGGER = logging.getLogger(__name__)

ENTITY_SUFFIX = "entity_suffix"
UPDATE_GROUP_FROM_CHILD_DELAY = 0.5


class BaseZhaEntity(LogMixin, entity.Entity):
    """A base class for ZHA entities."""

    unique_id_suffix: str | None = None
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, unique_id: str, zha_device: ZHADevice, **kwargs: Any) -> None:
        """Init ZHA entity."""
        self._name: str = ""
        self._force_update: bool = False
        self._unique_id: str = unique_id
        if self.unique_id_suffix:
            self._unique_id += f"-{self.unique_id_suffix}"
        self._state: Any = None
        self._extra_state_attributes: dict[str, Any] = {}
        self._zha_device = zha_device
        self._unsubs: list[Callable[[], None]] = []
        self.remove_future: asyncio.Future[Any] = asyncio.Future()

    @property
    def name(self) -> str:
        """Return Entity's default name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def zha_device(self) -> ZHADevice:
        """Return the zha device this entity is attached to."""
        return self._zha_device

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return self._extra_state_attributes

    @property
    def force_update(self) -> bool:
        """Force update this entity."""
        return self._force_update

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return a device description for device registry."""
        zha_device_info = self._zha_device.device_info
        ieee = zha_device_info["ieee"]
        return entity.DeviceInfo(
            connections={(CONNECTION_ZIGBEE, ieee)},
            identifiers={(DOMAIN, ieee)},
            manufacturer=zha_device_info[ATTR_MANUFACTURER],
            model=zha_device_info[ATTR_MODEL],
            name=zha_device_info[ATTR_NAME],
            via_device=(DOMAIN, self.hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID]),
        )

    @callback
    def async_state_changed(self) -> None:
        """Entity state changed."""
        self.async_write_ha_state()

    @callback
    def async_update_state_attribute(self, key: str, value: Any) -> None:
        """Update a single device state attribute."""
        self._extra_state_attributes.update({key: value})
        self.async_write_ha_state()

    @callback
    def async_set_state(self, attr_id: int, attr_name: str, value: Any) -> None:
        """Set the entity state."""

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        for unsub in self._unsubs[:]:
            unsub()
            self._unsubs.remove(unsub)

    @callback
    def async_accept_signal(
        self,
        channel: ZigbeeChannel | None,
        signal: str,
        func: Callable[..., Any],
        signal_override=False,
    ):
        """Accept a signal from a channel."""
        unsub = None
        if signal_override:
            unsub = async_dispatcher_connect(self.hass, signal, func)
        else:
            assert channel
            unsub = async_dispatcher_connect(
                self.hass, f"{channel.unique_id}_{signal}", func
            )
        self._unsubs.append(unsub)

    def log(self, level: int, msg: str, *args, **kwargs):
        """Log a message."""
        msg = f"%s: {msg}"
        args = (self.entity_id,) + args
        _LOGGER.log(level, msg, *args, **kwargs)


class ZhaEntity(BaseZhaEntity, RestoreEntity):
    """A base class for non group ZHA entities."""

    def __init_subclass__(cls, id_suffix: str | None = None, **kwargs: Any) -> None:
        """Initialize subclass.

        :param id_suffix: suffix to add to the unique_id of the entity. Used for multi
                          entities using the same channel/cluster id for the entity.
        """
        super().__init_subclass__(**kwargs)
        if id_suffix:
            cls.unique_id_suffix = id_suffix

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> None:
        """Init ZHA entity."""
        super().__init__(unique_id, zha_device, **kwargs)
        self._name: str = (
            self.__class__.__name__.lower()
            .replace("zha", "")
            .replace("entity", "")
            .replace("sensor", "")
            .capitalize()
        )
        self.cluster_channels: dict[str, ZigbeeChannel] = {}
        for channel in channels:
            self.cluster_channels[channel.name] = channel

    @classmethod
    def create_entity(
        cls: type[_ZhaEntitySelfT],
        unique_id: str,
        zha_device: ZHADevice,
        channels: list[ZigbeeChannel],
        **kwargs: Any,
    ) -> _ZhaEntitySelfT | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        return cls(unique_id, zha_device, channels, **kwargs)

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._zha_device.available

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        self.remove_future = asyncio.Future()
        self.async_accept_signal(
            None,
            f"{SIGNAL_REMOVE}_{self.zha_device.ieee}",
            functools.partial(self.async_remove, force_remove=True),
            signal_override=True,
        )

        if last_state := await self.async_get_last_state():
            self.async_restore_last_state(last_state)

        self.async_accept_signal(
            None,
            f"{self.zha_device.available_signal}_entity",
            self.async_state_changed,
            signal_override=True,
        )
        self._zha_device.gateway.register_entity_reference(
            self._zha_device.ieee,
            self.entity_id,
            self._zha_device,
            self.cluster_channels,
            self.device_info,
            self.remove_future,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        await super().async_will_remove_from_hass()
        self.zha_device.gateway.remove_entity_reference(self)
        self.remove_future.set_result(True)

    @callback
    def async_restore_last_state(self, last_state) -> None:
        """Restore previous state."""

    async def async_update(self) -> None:
        """Retrieve latest state."""
        tasks = [
            channel.async_update()
            for channel in self.cluster_channels.values()
            if hasattr(channel, "async_update")
        ]
        if tasks:
            await asyncio.gather(*tasks)


class ZhaGroupEntity(BaseZhaEntity):
    """A base class for ZHA group entities."""

    def __init__(
        self,
        entity_ids: list[str],
        unique_id: str,
        group_id: int,
        zha_device: ZHADevice,
        **kwargs: Any,
    ) -> None:
        """Initialize a light group."""
        super().__init__(unique_id, zha_device, **kwargs)
        self._available = False
        self._group = zha_device.gateway.groups.get(group_id)
        self._name = (
            f"{self._group.name}_zha_group_0x{group_id:04x}".lower().capitalize()
        )
        self._group_id: int = group_id
        self._entity_ids: list[str] = entity_ids
        self._async_unsub_state_changed: CALLBACK_TYPE | None = None
        self._handled_group_membership = False
        self._change_listener_debouncer: Debouncer | None = None

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._available

    @classmethod
    def create_entity(
        cls: type[_ZhaGroupEntitySelfT],
        entity_ids: list[str],
        unique_id: str,
        group_id: int,
        zha_device: ZHADevice,
        **kwargs: Any,
    ) -> _ZhaGroupEntitySelfT | None:
        """Group Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        return cls(entity_ids, unique_id, group_id, zha_device, **kwargs)

    async def _handle_group_membership_changed(self):
        """Handle group membership changed."""
        # Make sure we don't call remove twice as members are removed
        if self._handled_group_membership:
            return

        self._handled_group_membership = True
        await self.async_remove(force_remove=True)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        await self.async_update()

        self.async_accept_signal(
            None,
            f"{SIGNAL_GROUP_MEMBERSHIP_CHANGE}_0x{self._group_id:04x}",
            self._handle_group_membership_changed,
            signal_override=True,
        )

        if self._change_listener_debouncer is None:
            self._change_listener_debouncer = Debouncer(
                self.hass,
                _LOGGER,
                cooldown=UPDATE_GROUP_FROM_CHILD_DELAY,
                immediate=False,
                function=functools.partial(self.async_update_ha_state, True),
            )
        self._async_unsub_state_changed = async_track_state_change_event(
            self.hass, self._entity_ids, self.async_state_changed_listener
        )

        def send_removed_signal():
            async_dispatcher_send(
                self.hass, SIGNAL_GROUP_ENTITY_REMOVED, self._group_id
            )

        self.async_on_remove(send_removed_signal)

    @callback
    def async_state_changed_listener(self, event: Event):
        """Handle child updates."""
        # Delay to ensure that we get updates from all members before updating the group
        assert self._change_listener_debouncer
        self.hass.create_task(self._change_listener_debouncer.async_call())

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal from Home Assistant."""
        await super().async_will_remove_from_hass()
        if self._async_unsub_state_changed is not None:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    async def async_update(self) -> None:
        """Update the state of the group entity."""

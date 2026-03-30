"""Onkyo coordinators."""

from __future__ import annotations

import asyncio
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, cast

from aioonkyo import Kind, Status, Zone, command, query, status

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .receiver import ReceiverManager

if TYPE_CHECKING:
    from . import OnkyoConfigEntry

_LOGGER = logging.getLogger(__name__)


POWER_ON_QUERY_DELAY = 4


class Channel(StrEnum):
    """Audio channel."""

    FRONT_LEFT = "front_left"
    FRONT_RIGHT = "front_right"
    CENTER = "center"
    SURROUND_LEFT = "surround_left"
    SURROUND_RIGHT = "surround_right"
    SURROUND_BACK_LEFT = "surround_back_left"
    SURROUND_BACK_RIGHT = "surround_back_right"
    SUBWOOFER = "subwoofer"
    HEIGHT_1_LEFT = "height_1_left"
    HEIGHT_1_RIGHT = "height_1_right"
    HEIGHT_2_LEFT = "height_2_left"
    HEIGHT_2_RIGHT = "height_2_right"
    SUBWOOFER_2 = "subwoofer_2"


ChannelMutingData = dict[Channel, status.ChannelMuting.Param]
ChannelMutingDesired = dict[Channel, command.ChannelMuting.Param]


class ChannelMutingCoordinator(DataUpdateCoordinator[ChannelMutingData]):
    """Coordinator for channel muting state."""

    config_entry: OnkyoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OnkyoConfigEntry,
        manager: ReceiverManager,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="onkyo_channel_muting",
            update_interval=None,
        )

        self.manager = manager

        self.data = ChannelMutingData()
        self._desired = ChannelMutingDesired()

        self._entities_added = False

        self._query_state_task: asyncio.Task[None] | None = None

        manager.callbacks.connect.append(self._connect_callback)
        manager.callbacks.disconnect.append(self._disconnect_callback)
        manager.callbacks.update.append(self._update_callback)

        config_entry.async_on_unload(self._cancel_tasks)

    async def _connect_callback(self, _reconnect: bool) -> None:
        """Receiver (re)connected."""
        await self.manager.write(query.ChannelMuting())

    async def _disconnect_callback(self) -> None:
        """Receiver disconnected."""
        self._cancel_tasks()
        self.async_set_updated_data(self.data)

    def _cancel_tasks(self) -> None:
        """Cancel the tasks."""
        if self._query_state_task is not None:
            self._query_state_task.cancel()
            self._query_state_task = None

    def _query_state(self, delay: float = 0) -> None:
        """Query the receiver for all the info, that we care about."""
        if self._query_state_task is not None:
            self._query_state_task.cancel()
            self._query_state_task = None

        async def coro() -> None:
            if delay:
                await asyncio.sleep(delay)
            await self.manager.write(query.ChannelMuting())
            self._query_state_task = None

        self._query_state_task = asyncio.create_task(coro())

    async def _async_update_data(self) -> ChannelMutingData:
        """Respond to a data update request."""
        self._query_state()
        return self.data

    async def async_send_command(
        self, channel: Channel, param: command.ChannelMuting.Param
    ) -> None:
        """Send muting command for a channel."""
        self._desired[channel] = param
        message_data: ChannelMutingDesired = self.data | self._desired
        message = command.ChannelMuting(**message_data)  # type: ignore[misc]
        await self.manager.write(message)

    async def _update_callback(self, message: Status) -> None:
        """New message from the receiver."""
        match message:
            case status.NotAvailable(kind=Kind.CHANNEL_MUTING):
                not_available = True
            case status.ChannelMuting():
                not_available = False
            case status.Power(zone=Zone.MAIN, param=status.Power.Param.ON):
                self._query_state(POWER_ON_QUERY_DELAY)
                return
            case _:
                return

        if not self._entities_added:
            _LOGGER.debug(
                "Discovered %s on %s (%s)",
                self.name,
                self.manager.info.model_name,
                self.manager.info.host,
            )
            self._entities_added = True
            async_dispatcher_send(
                self.hass,
                f"{DOMAIN}_{self.config_entry.entry_id}_channel_muting",
                self,
            )

        if not_available:
            self.data.clear()
            self._desired.clear()
            self.async_set_updated_data(self.data)
        else:
            message = cast(status.ChannelMuting, message)
            self.data = {channel: getattr(message, channel) for channel in Channel}
            self._desired = {
                channel: desired
                for channel, desired in self._desired.items()
                if self.data[channel] != desired
            }
            self.async_set_updated_data(self.data)

"""Live bus state shared by the entities of one TIS Control config entry."""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from tis_smartbus import Telegram, TISGateway, commands as cmd

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import POLL_INTERVAL

if TYPE_CHECKING:
    from . import TISConfigEntry

_LOGGER = logging.getLogger(__name__)

type Address = tuple[int, int]


class TISHub:
    """Keep the last known level of every channel and tell entities when it changes.

    Modules announce most changes on the bus themselves (wall switches, panels, other apps), so state is
    pushed. Each module is also read every POLL_INTERVAL so a missed announcement heals itself, and a
    module that stops answering is reported unavailable.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TISConfigEntry,
        gateway: TISGateway,
        devices: list[dict[str, Any]],
    ) -> None:
        """Initialize the hub."""
        self.hass = hass
        self.entry = entry
        self.gateway = gateway
        self.devices = devices
        self.channels: dict[tuple[int, int, int], int] = {}
        self.online: dict[Address, bool] = {}
        self._subscribers: dict[Address, list[Callable[[], None]]] = defaultdict(list)
        self._unsubs: list[CALLBACK_TYPE] = []
        self._modules: set[Address] = {(d["subnet"], d["device"]) for d in devices}

    async def async_start(self) -> None:
        """Start listening to the bus and read every module once."""
        self._unsubs.append(self.gateway.add_listener(self._on_telegram))
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_poll, POLL_INTERVAL, name="TIS Control poll"
            )
        )
        await self._async_poll()

    async def async_stop(self) -> None:
        """Stop listening and close the connection."""
        while self._unsubs:
            self._unsubs.pop()()
        await self.gateway.close()

    @callback
    def subscribe(self, address: Address, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Call update whenever the module at address changes."""
        self._subscribers[address].append(update)

        @callback
        def remove() -> None:
            self._subscribers[address].remove(update)

        return remove

    def is_online(self, address: Address) -> bool:
        """Return whether the module answered its last read."""
        return self.online.get(address, False)

    async def _async_poll(self, _now: datetime | None = None) -> None:
        targets = sorted(self._modules)
        results = await asyncio.gather(
            *(self.gateway.read_channels(*address) for address in targets)
        )
        for address, levels in zip(targets, results, strict=True):
            was_online = self.online.get(address)
            self.online[address] = levels is not None
            if levels is None:
                if was_online is not False:
                    _LOGGER.info("TIS module %s.%s is not answering", *address)
                    self._notify(address)
                continue
            if was_online is False:
                _LOGGER.info("TIS module %s.%s is answering again", *address)
            for channel, level in enumerate(levels, start=1):
                self.channels[(*address, channel)] = level
            self._notify(address)

    @callback
    def _on_telegram(self, telegram: Telegram) -> None:
        address = telegram.source
        if address not in self._modules:
            return
        levels = cmd.decode_channel_levels(telegram.opcode, telegram.content)
        if not levels:
            return
        for item in levels:
            self.channels[(*address, item.channel)] = item.level
        self.online[address] = True
        self._notify(address)

    @callback
    def _notify(self, address: Address) -> None:
        for update in list(self._subscribers.get(address, ())):
            update()

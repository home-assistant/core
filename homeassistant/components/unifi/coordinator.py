"""UniFi Network data update coordinator."""

from datetime import timedelta
from typing import TYPE_CHECKING, override

from aiounifi.interfaces.api_handlers import APIHandler

import asyncio

from aiounifi.models.speedtest import SpeedtestStatus

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

if TYPE_CHECKING:
    from .hub.hub import UnifiHub

POLL_INTERVAL = timedelta(seconds=10)


class UnifiDataUpdateCoordinator[HandlerT: APIHandler](DataUpdateCoordinator[None]):
    """Coordinator managing polling for a single UniFi API data source."""

    def __init__(
        self,
        hub: UnifiHub,
        handler: HandlerT,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hub.hass,
            LOGGER,
            name=f"UniFi {type(handler).__name__}",
            config_entry=hub.config.entry,
            update_interval=POLL_INTERVAL,
        )
        self._handler = handler

    @property
    def handler(self) -> HandlerT:
        """Return the aiounifi handler managed by this coordinator."""
        return self._handler

    @override
    async def _async_update_data(self) -> None:
        """Update data from the API handler."""
        await self._handler.update()


class UnifiSpeedtestCoordinator(
    DataUpdateCoordinator[dict[str, SpeedtestStatus] | None]
):
    """Speedtest coordinator for UniFi."""

    def __init__(self, hass: HomeAssistant, hub: UnifiHub) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="UniFi Speedtest",
            update_interval=hub.config.option_speedtest_interval,
            always_update=False,
            config_entry=hub.config.entry,
        )
        self.hub = hub
        self._first_refresh = True

        hub.config.entry.async_on_unload(
            async_dispatcher_connect(
                hass,
                hub.signal_options_update,
                self.async_signal_options_updated,
            )
        )

    @callback
    def async_signal_options_updated(self) -> None:
        """Update interval upon options change."""
        if self.update_interval != self.hub.config.option_speedtest_interval:
            self.update_interval = self.hub.config.option_speedtest_interval
            self.async_set_updated_data(self.data)  # trigger reschedule

    async def _async_update_data(self) -> dict[str, SpeedtestStatus] | None:
        """Trigger a speedtest and wait for it to finish."""
        if self._first_refresh:
            self._first_refresh = False
            await self.hub.api.speedtest.update()
            if not self.hub.api.speedtest.values():
                return None
            return dict(self.hub.api.speedtest.items())

        # Get the current latest speedtest timestamp per interface before triggering
        await self.hub.api.speedtest.update()
        start_times = {
            interface_name: status.timestamp
            for interface_name, status in self.hub.api.speedtest.items()
        }

        # Trigger the speed test
        await self.hub.api.speedtest.trigger()

        # Unifi UI implies test takes ~20 to 30 seconds.
        # We poll every 5 seconds until at least one timestamp updates (or timeout).
        for _ in range(12):  # 12 iterations * 5 = 60 seconds
            await asyncio.sleep(5)
            await self.hub.api.speedtest.update()

            # Check if any interface's timestamp has advanced
            has_advanced = any(
                status.timestamp > start_times.get(interface_name, 0)
                for interface_name, status in self.hub.api.speedtest.items()
            )

            if has_advanced:
                break

        if not self.hub.api.speedtest.values():
            return None
        return dict(self.hub.api.speedtest.items())

"""Coordinate polling and commands for a Heiman Wi-Fi switch."""

from asyncio import Lock
from datetime import timedelta
import logging
from typing import override

from heiman_local_client import HeimanError, HeimanSwitchClient, SwitchInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type HeimanConfigEntry = ConfigEntry[HeimanCoordinator]


class HeimanCoordinator(DataUpdateCoordinator[bool]):
    """Keep the switch state synchronized with the device."""

    def __init__(
        self, hass: HomeAssistant, entry: HeimanConfigEntry, client: HeimanSwitchClient
    ) -> None:
        """Initialize the poller."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=30),
            always_update=False,
        )
        self._client = client
        self._expected_mac = entry.unique_id
        self._io_lock = Lock()
        self.info: SwitchInfo

    async def _get_matching_info(self) -> SwitchInfo:
        info = await self._client.get_info()
        if info.mac != self._expected_mac:
            raise HeimanError(
                "The switch at the configured address has a different MAC"
            )
        return info

    @override
    async def _async_setup(self) -> None:
        """Read device information before setting up the switch entity."""
        try:
            self.info = await self._get_matching_info()
        except HeimanError as err:
            raise UpdateFailed(str(err)) from err

    @override
    async def _async_update_data(self) -> bool:
        """Poll the device state."""
        async with self._io_lock:
            try:
                info = await self._get_matching_info()
                return await self._client.get_power(info)
            except HeimanError as err:
                raise UpdateFailed(str(err)) from err

    async def async_set_power(self, is_on: bool) -> None:
        """Apply a command and publish only the value read back from the switch."""
        async with self._io_lock:
            try:
                # DHCP may have reassigned the configured IP since setup.
                info = await self._get_matching_info()
                await self._client.set_power(is_on)
                actual = await self._client.get_power(info)
            except HeimanError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="set_power_failed"
                ) from err

            self.async_set_updated_data(actual)
            if actual != is_on:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="set_power_failed"
                )

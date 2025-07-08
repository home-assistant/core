"""Coordinator module for Miele integration."""

from __future__ import annotations

import asyncio.timeouts
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging

from pymiele import MieleAction, MieleDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AsyncConfigEntryAuth
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type MieleConfigEntry = ConfigEntry[MieleDataUpdateCoordinator]


@dataclass
class MieleCoordinatorData:
    """Data class for storing coordinator data."""

    devices: dict[str, MieleDevice]
    actions: dict[str, MieleAction]


class MieleDataUpdateCoordinator(DataUpdateCoordinator[MieleCoordinatorData]):
    """Coordinator for Miele data."""

    config_entry: MieleConfigEntry
    new_device_callbacks: list[Callable[[dict[str, MieleDevice]], None]] = []
    known_devices: set[str] = set()
    devices: dict[str, MieleDevice] = {}

    def __init__(
        self,
        hass: HomeAssistant,
        api: AsyncConfigEntryAuth,
    ) -> None:
        """Initialize the Miele data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=120),
        )
        self.api = api

    async def _async_update_data(self) -> MieleCoordinatorData:
        """Fetch data from the Miele API."""
        async with asyncio.timeout(10):
            # Get devices
            devices_json = await self.api.get_devices()
            devices = {
                device_id: MieleDevice(device)
                for device_id, device in devices_json.items()
            }
            self.devices = devices
            actions = {}
            for device_id in devices:
                actions_json = await self.api.get_actions(device_id)
                actions[device_id] = MieleAction(actions_json)
            return MieleCoordinatorData(devices=devices, actions=actions)

    def async_add_devices(self, added_devices: set[str]) -> tuple[set[str], set[str]]:
        """Add devices."""
        current_devices = set(self.devices)
        new_devices: set[str] = current_devices - added_devices

        return (new_devices, current_devices)

    async def callback_update_data(self, devices_json: dict[str, dict]) -> None:
        """Handle data update from the API."""
        devices = {
            device_id: MieleDevice(device) for device_id, device in devices_json.items()
        }
        self.async_set_updated_data(
            MieleCoordinatorData(
                devices=devices,
                actions=self.data.actions,
            )
        )

    async def callback_update_actions(self, actions_json: dict[str, dict]) -> None:
        """Handle data update from the API."""
        actions = {
            device_id: MieleAction(action) for device_id, action in actions_json.items()
        }
        self.async_set_updated_data(
            MieleCoordinatorData(
                devices=self.data.devices,
                actions=actions,
            )
        )

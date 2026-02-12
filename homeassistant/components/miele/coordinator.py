"""Coordinator module for Miele integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging

from aiohttp import ClientResponseError
from pymiele import (
    MieleAction,
    MieleAPI,
    MieleDevice,
    MieleFailureData,
    MieleFillingLevel,
    MieleFillingLevels,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class MieleRuntimeData:
    """Runtime data for the Miele integration."""

    api: MieleAPI
    coordinator: MieleDataUpdateCoordinator
    aux_coordinator: MieleAuxDataUpdateCoordinator
    failure_coordinator: MieleFailureDataUpdateCoordinator


type MieleConfigEntry = ConfigEntry[MieleRuntimeData]


@dataclass
class MieleCoordinatorData:
    """Data class for storing coordinator data."""

    devices: dict[str, MieleDevice]
    actions: dict[str, MieleAction]


@dataclass
class MieleAuxCoordinatorData:
    """Data class for storing auxiliary coordinator data."""

    filling_levels: dict[str, MieleFillingLevel]


class MieleDataUpdateCoordinator(DataUpdateCoordinator[MieleCoordinatorData]):
    """Main coordinator for Miele data."""

    config_entry: MieleConfigEntry
    new_device_callbacks: list[Callable[[dict[str, MieleDevice]], None]] = []
    known_devices: set[str] = set()
    failing_devices: set[str] = set()
    devices: dict[str, MieleDevice] = {}

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MieleConfigEntry,
        api: MieleAPI,
    ) -> None:
        """Initialize the Miele data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
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

            for device_id, device in devices.items():
                # actions are fetched separately
                try:
                    actions_json = await self.api.get_actions(device_id)
                except ClientResponseError as err:
                    _LOGGER.debug(
                        "Error fetching actions for device %s: Status: %s, Message: %s",
                        device_id,
                        str(err.status),
                        err.message,
                    )
                    actions_json = {}
                except TimeoutError:
                    _LOGGER.debug(
                        "Timeout fetching actions for device %s",
                        device_id,
                    )
                    actions_json = {}
                actions[device_id] = MieleAction(actions_json)

                # failures are not fetched, but they trigger failure_coordinator to fetch details
                has_failure = device.state_signal_failure
                if has_failure and device_id not in self.failing_devices:
                    self.failing_devices.add(device_id)
                    self.hass.async_create_task(
                        self.config_entry.runtime_data.failure_coordinator.async_fetch_failure(
                            device_id
                        )
                    )
                elif not has_failure and device_id in self.failing_devices:
                    self.failing_devices.remove(device_id)
                    self.config_entry.runtime_data.failure_coordinator.clear_failure(
                        device_id
                    )

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
            MieleCoordinatorData(devices=devices, actions=self.data.actions)
        )

    async def callback_update_actions(self, actions_json: dict[str, dict]) -> None:
        """Handle data update from the API."""
        actions = {
            device_id: MieleAction(action) for device_id, action in actions_json.items()
        }
        self.async_set_updated_data(
            MieleCoordinatorData(devices=self.data.devices, actions=actions)
        )


class MieleAuxDataUpdateCoordinator(DataUpdateCoordinator[MieleAuxCoordinatorData]):
    """Coordinator for Miele data for slowly polled endpoints."""

    config_entry: MieleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MieleConfigEntry,
        api: MieleAPI,
    ) -> None:
        """Initialize the Miele data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.api = api

    async def _async_update_data(self) -> MieleAuxCoordinatorData:
        """Fetch data from the Miele API."""
        filling_levels_json = await self.api.get_filling_levels()
        return MieleAuxCoordinatorData(
            filling_levels=MieleFillingLevels(filling_levels_json).filling_levels
        )


class MieleFailureDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for Miele data for failure endpoint, polled when needed."""

    config_entry: MieleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MieleConfigEntry,
        api: MieleAPI,
    ) -> None:
        """Initialize the Miele data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.api = api
        self.data: dict[str, MieleFailureData | None] = {}

    async def _async_update_data(self) -> dict[str, MieleFailureData | None]:
        """Update data is not fetched on an interval, but on demand."""
        return self.data

    async def async_fetch_failure(self, device_id: str) -> None:
        """Fetch failure data for a device from the Miele API."""
        try:
            failure_json = await self.api.get_failure_details(device_id)
            self.data[device_id] = MieleFailureData(failure_json)
        except ClientResponseError as err:
            _LOGGER.debug(
                "Error fetching failure data for device %s: Status: %s, Message: %s",
                device_id,
                str(err.status),
                err.message,
            )
            self.data[device_id] = None
        except TimeoutError:
            _LOGGER.debug(
                "Timeout fetching failure data for device %s",
                device_id,
            )
            self.data[device_id] = None
        self.async_set_updated_data(self.data)

    def clear_failure(self, device_id: str) -> None:
        """Clear failure data for a device."""
        if device_id in self.data:
            self.data[device_id] = None
            self.async_set_updated_data(self.data)

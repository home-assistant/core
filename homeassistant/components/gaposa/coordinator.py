"""Data update coordinator for the Gaposa integration."""

from __future__ import annotations

from asyncio import timeout
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aiohttp import ClientError
from pygaposa import Device, FirebaseAuthException, Gaposa, GaposaAuthException, Motor

from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL, UPDATE_INTERVAL_FAST

if TYPE_CHECKING:
    from . import GaposaConfigEntry

_LOGGER = logging.getLogger(__name__)


class DataUpdateCoordinatorGaposa(DataUpdateCoordinator[dict[str, Motor]]):
    """Fetch state for every Gaposa motor on the account."""

    config_entry: GaposaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GaposaConfigEntry,
        *,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.gaposa: Gaposa | None = None
        self.devices: list[Device] = []
        self._listener: Callable[[], None] | None = None

    async def _async_setup(self) -> None:
        """Log in to the Gaposa API once, before the first refresh."""
        websession = async_get_clientsession(self.hass)
        gaposa = Gaposa(self.config_entry.data[CONF_API_KEY], websession=websession)
        try:
            async with timeout(10):
                await gaposa.login(
                    self.config_entry.data[CONF_USERNAME],
                    self.config_entry.data[CONF_PASSWORD],
                )
        except (GaposaAuthException, FirebaseAuthException) as exc:
            await gaposa.close()
            raise ConfigEntryNotReady("Gaposa authentication failed") from exc
        except (ClientError, TimeoutError, OSError) as exc:
            await gaposa.close()
            raise ConfigEntryNotReady(f"Error connecting to Gaposa: {exc}") from exc
        self.gaposa = gaposa

    async def _async_update_data(self) -> dict[str, Motor]:
        """Refresh motor state from the Gaposa cloud."""
        assert self.gaposa is not None  # set in _async_setup

        try:
            async with timeout(10):
                await self.gaposa.update()
        except (
            GaposaAuthException,
            FirebaseAuthException,
            ClientError,
            TimeoutError,
            OSError,
        ) as exc:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)
            raise UpdateFailed(f"Error talking to Gaposa: {exc}") from exc

        # pygaposa polls the Firestore REST API internally after commands
        # (every 2 s for ~20 s). Register a listener on each device so
        # those rapid post-command polls push fresh data to our entities
        # via async_set_updated_data, rather than waiting for the next
        # coordinator poll (600 s).
        if self._listener is None:
            self._listener = self._on_device_polled

        current_devices: list[Device] = []
        for client, _user in self.gaposa.clients:
            for device in client.devices:
                current_devices.append(device)
                if device not in self.devices:
                    device.addListener(self._listener)

        for device in self.devices:
            if device not in current_devices:
                device.removeListener(self._listener)

        self.devices = current_devices

        self.update_interval = timedelta(seconds=UPDATE_INTERVAL)

        return self._get_data_from_devices()

    def _get_data_from_devices(self) -> dict[str, Motor]:
        """Flatten all motors across all devices into a single dict.

        The dictionary key is a unique id for the motor of the form
        ``<device serial number>.motors.<motor.id>``.
        """
        data: dict[str, Motor] = {}
        if self.gaposa is None:
            return data
        for client, _user in self.gaposa.clients:
            for device in client.devices:
                for motor in device.motors:
                    data[f"{device.serial}.motors.{motor.id}"] = motor
        return data

    def _on_device_polled(self) -> None:
        """Called by pygaposa after each internal poll of a device document.

        This fires during pygaposa's rapid post-command polling (every ~2 s)
        and pushes the latest motor state to all coordinator subscribers
        without waiting for the next scheduled coordinator refresh.
        """
        _LOGGER.debug("Gaposa device polled, pushing new data")
        self.async_set_updated_data(self._get_data_from_devices())

    async def async_shutdown(self) -> None:
        """Detach listeners and close the Gaposa session."""
        await super().async_shutdown()
        if self._listener is not None:
            for device in self.devices:
                device.removeListener(self._listener)
            self._listener = None
        self.devices = []
        if self.gaposa is not None:
            await self.gaposa.close()
            self.gaposa = None

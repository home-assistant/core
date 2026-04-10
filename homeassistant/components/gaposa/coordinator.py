"""Data update coordinator for the Gaposa integration."""

from __future__ import annotations

from asyncio import timeout
from collections.abc import Callable
from datetime import timedelta
import logging

from aiohttp import ClientError
from pygaposa import Device, FirebaseAuthException, Gaposa, GaposaAuthException, Motor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL, UPDATE_INTERVAL_FAST

_LOGGER = logging.getLogger(__name__)


class DataUpdateCoordinatorGaposa(DataUpdateCoordinator[dict[str, Motor]]):
    """Fetch state for every Gaposa motor on the account."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        *,
        api_key: str,
        username: str,
        password: str,
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
        self._api_key = api_key
        self._username = username
        self._password = password
        self.gaposa: Gaposa | None = None
        self.devices: list[Device] = []
        self._listener: Callable[[], None] | None = None

    async def _async_setup(self) -> None:
        """Log in to the Gaposa API once, before the first refresh.

        ``DataUpdateCoordinator`` calls this method exactly once as part
        of ``async_config_entry_first_refresh``, so it's the right place
        to do any one-time connection / authentication work.
        """
        websession = async_get_clientsession(self.hass)
        self.gaposa = Gaposa(self._api_key, websession=websession)
        try:
            await self.gaposa.login(self._username, self._password)
        except (GaposaAuthException, FirebaseAuthException) as exc:
            raise ConfigEntryAuthFailed(
                "Gaposa authentication failed"
            ) from exc

    async def _async_update_data(self) -> dict[str, Motor]:
        """Refresh motor state from the Gaposa cloud."""
        assert self.gaposa is not None  # set in _async_setup

        try:
            async with timeout(10):
                await self.gaposa.update()
        except (GaposaAuthException, FirebaseAuthException) as exc:
            raise ConfigEntryAuthFailed(
                "Gaposa authentication failed"
            ) from exc
        except (ClientError, TimeoutError, OSError) as exc:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)
            raise UpdateFailed(f"Error talking to Gaposa: {exc}") from exc

        # Attach a listener to every new device so document-level pushes
        # from pygaposa trigger async_set_updated_data.
        if self._listener is None:
            self._listener = self.on_document_updated

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

        # Recovered from a transient failure — restore the normal interval.
        self.update_interval = timedelta(seconds=UPDATE_INTERVAL)

        return self._get_data_from_devices()

    def _get_data_from_devices(self) -> dict[str, Motor]:
        """Flatten all motors across all devices into a single dict.

        The dictionary key is a unique id for the motor of the form
        ``<device serial number>.motors.<channel number>``.
        """
        data: dict[str, Motor] = {}
        if self.gaposa is None:
            return data
        for client, _user in self.gaposa.clients:
            for device in client.devices:
                for motor in device.motors:
                    data[f"{device.serial}.motors.{motor.id}"] = motor
        return data

    def on_document_updated(self) -> None:
        """Push fresh data to subscribers when pygaposa notifies us."""
        _LOGGER.debug("Gaposa document updated, pushing new data")
        self.async_set_updated_data(self._get_data_from_devices())

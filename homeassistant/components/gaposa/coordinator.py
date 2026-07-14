"""Data update coordinator for the Gaposa integration."""

from asyncio import timeout
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from aiohttp import ClientError
from pygaposa import Device, FirebaseAuthException, Gaposa, GaposaAuthException, Motor

from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL, UPDATE_INTERVAL_FAST

if TYPE_CHECKING:
    from . import GaposaConfigEntry

_LOGGER = logging.getLogger(__name__)


class DataUpdateCoordinatorGaposa(DataUpdateCoordinator[dict[str, Motor]]):
    """Fetch state for every Gaposa motor on the account."""

    config_entry: GaposaConfigEntry
    gaposa: Gaposa

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GaposaConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.devices: list[Device] = []
        self._listener: Callable[[], None] | None = None
        self._updating = False

    @override
    async def _async_setup(self) -> None:
        """Log in to the Gaposa API once, before the first refresh.

        Assign self.gaposa before awaiting login so async_shutdown
        (called from async_setup_entry on any failure, including
        cancellation) can find and close the client.
        """
        websession = async_get_clientsession(self.hass)
        self.gaposa = Gaposa(
            self.config_entry.data[CONF_API_KEY], websession=websession
        )
        try:
            async with timeout(10):
                await self.gaposa.login(
                    self.config_entry.data[CONF_USERNAME],
                    self.config_entry.data[CONF_PASSWORD],
                )
        except (GaposaAuthException, FirebaseAuthException) as exc:
            raise ConfigEntryAuthFailed("Gaposa authentication failed") from exc
        except (ClientError, TimeoutError, OSError) as exc:
            raise ConfigEntryNotReady(f"Error connecting to Gaposa: {exc}") from exc

    @override
    async def _async_update_data(self) -> dict[str, Motor]:
        """Refresh motor state from the Gaposa cloud."""
        # Gaposa.update() no longer fires per-device listeners itself
        # (pygaposa 0.2.5 defaults notifyListeners=False). The gate is
        # still needed to suppress command-driven listener pushes from
        # pygaposa's fire-and-forget post-command polls that might run
        # concurrently with a scheduled update() — otherwise each one
        # publishes an intermediate flatten before we return.
        self._updating = True
        try:
            async with timeout(10):
                await self.gaposa.update()
        except (GaposaAuthException, FirebaseAuthException) as exc:
            # Signal reauth (if configured) instead of tight retry —
            # a fast retry loop cannot recover from bad credentials.
            raise ConfigEntryAuthFailed(f"Gaposa authentication failed: {exc}") from exc
        except (ClientError, TimeoutError, OSError) as exc:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)
            raise UpdateFailed(f"Error talking to Gaposa: {exc}") from exc
        finally:
            self._updating = False

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

        The key ``<device serial>_<motor id>`` is unique across all
        motors on the account and is used as the cover unique_id.
        """
        data: dict[str, Motor] = {}
        for client, _user in self.gaposa.clients:
            for device in client.devices:
                for motor in device.motors:
                    data[f"{device.serial}_{motor.id}"] = motor
        return data

    def _on_device_polled(self) -> None:
        """Called by pygaposa's command-driven poll of a device document.

        Fires during the rapid post-command polling triggered by
        motor.up/down/stop (every ~2 s for ~20 s) and pushes the
        latest motor state to all coordinator subscribers without
        waiting for the next scheduled coordinator refresh.

        Scheduled updates don't fire this — pygaposa's Gaposa.update()
        defaults notifyListeners=False — but the _updating gate is
        kept as a safety net in case a command-driven poll fires
        while a scheduled refresh is also in flight.
        """
        if self._updating:
            return
        _LOGGER.debug("Gaposa device polled, pushing new data")
        self.async_set_updated_data(self._get_data_from_devices())

    @override
    async def async_shutdown(self) -> None:
        """Detach listeners and close the Gaposa session.

        Idempotent: base DataUpdateCoordinator registers an unload
        listener that also calls async_shutdown, and setup can fail
        before self.gaposa is assigned in _async_setup.
        """
        await super().async_shutdown()
        if self._listener is not None:
            for device in self.devices:
                device.removeListener(self._listener)
            self._listener = None
        self.devices = []
        gaposa = self.__dict__.pop("gaposa", None)
        if gaposa is not None:
            await gaposa.close()

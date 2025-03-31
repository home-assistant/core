"""Data update coordinator for the Gaposa integration."""

from asyncio import timeout
from collections.abc import Callable
from datetime import timedelta
import logging

from pygaposa import Device, FirebaseAuthException, Gaposa, GaposaAuthException, Motor

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL, UPDATE_INTERVAL_FAST


class DataUpdateCoordinatorGaposa(DataUpdateCoordinator):
    """Class to manage fetching data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        gaposa: Gaposa,
        *,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
        )

        self.gaposa = gaposa
        self.devices: list[Device] = []
        self.listener: Callable[[], None] | None = None

    async def update_gateway(self) -> bool:
        """Fetch data from gateway."""
        try:
            await self.gaposa.update()
        except GaposaAuthException as exp:
            raise ConfigEntryAuthFailed from exp
        except FirebaseAuthException as exp:
            raise ConfigEntryAuthFailed from exp

        current_devices: list[Device] = []
        new_devices: list[Device] = []
        if self.listener is None:
            self.listener = self.on_document_updated
            for client, _user in self.gaposa.clients:
                for device in client.devices:
                    current_devices.append(device)
                    if device not in self.devices:
                        device.addListener(self.listener)
                        new_devices.append(device)

        for device in self.devices:
            if device not in current_devices:
                device.removeListener(self.listener)

        self.devices = current_devices

        return True

    async def _async_update_data(self) -> dict[str, Motor]:
        self.logger.debug(
            "Gaposa coordinator _async_update_data, interval: %s",
            str(self.update_interval),
        )

        try:
            async with timeout(10):
                await self.update_gateway()
        except ConfigEntryAuthFailed:
            raise
        except TimeoutError:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)
            raise
        except Exception as exp:
            self.logger.exception("Error updating Gaposa data")
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)
            raise UpdateFailed from exp

        self.update_interval = timedelta(seconds=UPDATE_INTERVAL)

        data = self._get_data_from_devices()

        self.logger.debug("Finished _async_update_data")

        return data

    def _get_data_from_devices(self) -> dict[str, Motor]:
        # Coordinator data consists of a Dictionary of the controllable motors, with
        # the dictionalry key being a unique id for the motor of the form
        # <device serial number>.motors.<channel number>
        data: dict[str, Motor] = {}

        for client, _user in self.gaposa.clients:
            for device in client.devices:
                for motor in device.motors:
                    data[f"{device.serial}.motors.{motor.id}"] = motor

        return data

    def on_document_updated(self) -> None:
        """Handle document updated."""
        self.logger.debug("Gaposa coordinator on_document_updated")
        data = self._get_data_from_devices()
        self.async_set_updated_data(data)

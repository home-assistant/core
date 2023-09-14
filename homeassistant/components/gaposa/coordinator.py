"""Data update coordinator for the Gaposa integration."""
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TypedDict

from pygaposa import FirebaseAuthException, Gaposa, GaposaAuthException, Motor

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_FAST,
)


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
        self.listener: Callable[[], None] | None = None

    async def update_gateway(self):
        """Fetch data from gateway."""
        try:
            await self.gaposa.update()
        except GaposaAuthException as exp:
            raise ConfigEntryAuthFailed from exp
        except FirebaseAuthException as exp:
            raise ConfigEntryAuthFailed from exp

        if self.listener is None:
            self.listener = self.on_document_updated
            for client, _user in self.gaposa.clients:
                for device in client.devices:
                    device.addListener(self.listener)

        return True

    async def _async_update_data(self):
        try:
            result = await self.update_gateway()
        except ConfigEntryAuthFailed:
            raise
        except Exception as exp:
            raise UpdateFailed from exp

        if result:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL)
        else:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)

        # Coordinator data consists of a Dictionary of the controllable motors, with
        # the dictionalry key being a unique id for the motor of the form
        # <device serial number>.motors.<channel number>

        data: TypedDict[str, Motor] = {}

        for client, _user in self.gaposa.clients:
            for device in client.devices:
                for motor in device.motors:
                    data[f"%{device.serial}.motors.%{motor.id}"] = motor

        return data

    def on_document_updated(self):
        """Handle document updated."""
        for client, _user in self.gaposa.clients:
            for device in client.devices:
                for motor in device.motors:
                    motor.async_write_ha_state()

"""The CCL Data Update Coordinator."""

from datetime import timedelta
import logging
import time
from typing import override

from aioccl import CCLDevice, CCLSensor
from aioccl.exception import CCLDataUpdateException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_CHECKING_INTERVAL = 600

type CCLConfigEntry = ConfigEntry[CCLCoordinator]


class CCLCoordinator(DataUpdateCoordinator[dict[str, CCLSensor]]):
    """Class to manage processing CCL data."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: CCLDevice,
        entry: CCLConfigEntry,
    ) -> None:
        """Initialize global CCL data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=_CHECKING_INTERVAL),
            update_method=self._async_update_data,
            always_update=True,
        )

        self.device = device

    @override
    async def _async_update_data(self) -> dict[str, CCLSensor]:
        _LOGGER.debug(
            "Checking for device(%s) availability at %s",
            self.device.device_id,
            time.monotonic(),
        )

        last_update_time = self.device.last_update_time
        if last_update_time is None:
            return {}

        # Compare the last update time to the current time in monotonic time.
        if time.monotonic() - last_update_time >= _CHECKING_INTERVAL:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_timed_out",
            )
        try:
            return self.device.get_sensors()
        except CCLDataUpdateException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="error_updating_data",
                translation_placeholders={"error": str(err)},
            ) from err

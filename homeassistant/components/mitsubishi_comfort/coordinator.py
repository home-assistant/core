"""DataUpdateCoordinator for Mitsubishi Comfort devices."""

import logging
from typing import override

from mitsubishi_comfort import IndoorUnit, KumoStation

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type MitsubishiComfortConfigEntry = ConfigEntry[dict[str, MitsubishiComfortCoordinator]]


class MitsubishiComfortCoordinator(DataUpdateCoordinator[IndoorUnit | KumoStation]):
    """Coordinator to poll a single Mitsubishi device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MitsubishiComfortConfigEntry,
        device: IndoorUnit | KumoStation,
        mac: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"mitsubishi_comfort_{device.serial}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.device = device
        self.mac = mac
        self.data = device

    @override
    async def _async_update_data(self) -> IndoorUnit | KumoStation:
        """Poll the device and return it."""
        try:
            success = await self.device.update_status()
        except Exception as err:
            # The user-facing UpdateFailed message is translated and omits the IP;
            # log it here so the failing address is visible in debug logs.
            _LOGGER.debug(
                "Error polling %s at %s: %s",
                self.device.name,
                self.device.address,
                err,
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"device_name": self.device.name},
            ) from err
        if not success:
            _LOGGER.debug(
                "%s at %s returned no data", self.device.name, self.device.address
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"device_name": self.device.name},
            )
        return self.device

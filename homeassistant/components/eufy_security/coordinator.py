"""Data coordinators for the Eufy Security integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from eufy_security import (
    CaptchaRequiredError,
    EufySecurityAPI,
    EufySecurityError,
    InvalidCredentialsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class EufySecurityData:
    """Class to support type hinting of Eufy Security data collection."""

    api: EufySecurityAPI
    devices: dict[str, Any]
    coordinator: EufySecurityCoordinator


type EufySecurityConfigEntry = ConfigEntry[EufySecurityData]


class EufySecurityCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Eufy Security data update coordinator."""

    config_entry: EufySecurityConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EufySecurityConfigEntry,
        api: EufySecurityAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.api = api
        self._unavailable_logged = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            await self.api.async_update_device_info()
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except CaptchaRequiredError as err:
            # CAPTCHA required during refresh - trigger reauth flow
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except EufySecurityError as err:
            if not self._unavailable_logged:
                _LOGGER.warning(
                    "Eufy Security API is unavailable: %s",
                    err,
                )
                self._unavailable_logged = True
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

        # Log recovery if we were previously unavailable
        if self._unavailable_logged:
            _LOGGER.info("Eufy Security API connection restored")
            self._unavailable_logged = False

        return {
            "cameras": {camera.serial: camera for camera in self.api.cameras.values()},
            "stations": {
                station.serial: station for station in self.api.stations.values()
            },
        }

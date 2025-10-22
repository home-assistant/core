"""Coordinator for the SMA integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pysma import SMA
from pysma.exceptions import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
)
from pysma.sensor import Sensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SMACoordinatorData:
    """Data class for SMA sensors."""

    sma_device_info: dict[str, str]
    sensors: list[Sensor]


class SMADataUpdateCoordinator(DataUpdateCoordinator[SMACoordinatorData]):
    """Data Update Coordinator for SMA."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        sma: SMA,
    ) -> None:
        """Initialize the SMA Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
        )
        self.sma = sma
        self._sma_device_info: dict[str, str] = {}
        self._sensors: list[Sensor] = []

    async def _async_setup(self) -> None:
        """Setup the SMA Data Update Coordinator."""
        try:
            self._sma_device_info = await self.sma.device_info()
            self._sensors = await self.sma.get_sensors()
        except (
            SmaReadException,
            SmaConnectionException,
        ) as err:
            await self.async_close_sma_session()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except SmaAuthenticationException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def _async_update_data(self) -> SMACoordinatorData:
        """Update the used SMA sensors."""
        try:
            await self.sma.read(self._sensors)
        except (
            SmaReadException,
            SmaConnectionException,
        ) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except SmaAuthenticationException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err

        return SMACoordinatorData(
            sma_device_info=self._sma_device_info,
            sensors=self._sensors,
        )

    async def async_close_sma_session(self) -> None:
        """Close the SMA session."""
        await self.sma.close_session()
        _LOGGER.debug("SMA session closed")

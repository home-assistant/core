"""Coordinator for the SMA integration."""

from __future__ import annotations

import logging

from pysma import SMA
from pysma.exceptions import (
    SmaAuthenticationException,
    SmaConnectionException,
    SmaReadException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SMADataUpdateCoordinator(DataUpdateCoordinator):
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
            update_interval=config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        )
        self.sma = sma

    async def _async_setup(self) -> None:
        """Set up the SMA Data Update Coordinator."""
        try:
            sma_device_info = await self.sma.device_info()
            sensor_def = await self.sma.get_sensors()
        except (
            SmaReadException,
            SmaConnectionException,
        ) as err:
            await self.async_close_sma_session()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except SmaAuthenticationException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def _async_update_data(self) -> None:
        """Update the used SMA sensors."""
        try:
            # @Erwin: fetch the sensor data from the data
            await self.sma.read(sensor_def)
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

    async def async_close_sma_session(self) -> None:
        """Close the SMA session."""
        await self.sma.close_session()
        _LOGGER.debug("SMA session closed")

"""DataUpdateCoordinator for the LaMatric integration."""

from dataclasses import dataclass
from typing import override

from demetriek import (
    App,
    Device,
    LaMetricAuthenticationError,
    LaMetricDevice,
    LaMetricError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


@dataclass(kw_only=True)
class LaMetricRuntimeData:
    """Runtime data for the LaMetric integration."""

    device: LaMetricDataUpdateCoordinator
    apps: LaMetricAppsUpdateCoordinator


type LaMetricConfigEntry = ConfigEntry[LaMetricRuntimeData]


class LaMetricDataUpdateCoordinator(DataUpdateCoordinator[Device]):
    """The LaMetric Data Update Coordinator."""

    config_entry: LaMetricConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LaMetricConfigEntry) -> None:
        """Initialize the LaMatric coordinator."""
        self.lametric = LaMetricDevice(
            host=entry.data[CONF_HOST],
            api_key=entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        )

        super().__init__(
            hass, LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL
        )

    @override
    async def _async_update_data(self) -> Device:
        """Fetch device information of the LaMetric device."""
        try:
            return await self.lametric.device()
        except LaMetricAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except LaMetricError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex


class LaMetricAppsUpdateCoordinator(DataUpdateCoordinator[dict[str, App]]):
    """The LaMetric apps Data Update Coordinator."""

    config_entry: LaMetricConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LaMetricConfigEntry) -> None:
        """Initialize the LaMetric apps coordinator."""
        self.lametric = LaMetricDevice(
            host=entry.data[CONF_HOST],
            api_key=entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        )

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}-apps",
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, App]:
        """Fetch the apps installed on the LaMetric device."""
        try:
            return await self.lametric.apps()
        except LaMetricAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except LaMetricError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex

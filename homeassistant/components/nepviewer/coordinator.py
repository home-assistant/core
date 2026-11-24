"""DataUpdateCoordinator for the NEPViewer integration."""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aionepviewer import (
    Device,
    DeviceStatisticsOverview,
    Module,
    NepApiError,
    NepAuthError,
    NepConnectionError,
    NepViewer,
    Site,
    SiteDetail,
    SiteOverview,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

type NepViewerConfigEntry = ConfigEntry[NepViewerCoordinator]


@dataclass(kw_only=True, slots=True)
class NepViewerData:
    """Data returned by a single coordinator refresh."""

    sites: list[Site]
    devices: list[Device]
    site_overviews: dict[str, SiteOverview]
    device_overviews: dict[str, DeviceStatisticsOverview]
    # Outer key: device sn (uppercase). Inner key: module plc_sn.
    device_modules: dict[str, dict[str, Module]]
    site_details: dict[str, SiteDetail]


@contextmanager
def _translate_errors() -> Generator[None]:
    """Translate NEPViewer errors to Home Assistant errors."""
    try:
        yield
    except NepAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="auth_failed"
        ) from err
    except NepConnectionError as err:
        raise UpdateFailedUnreachable(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    except NepApiError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN, translation_key="api_error"
        ) from err


class NepViewerCoordinator(DataUpdateCoordinator[NepViewerData]):
    """Coordinator that polls the NEPViewer cloud API."""

    config_entry: NepViewerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NepViewerConfigEntry,
        client: NepViewer,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self._client = client
        self._sites: list[Site] = []
        self._devices: list[Device] = []
        self._site_details: dict[str, SiteDetail] = {}

    @override
    async def _async_setup(self) -> None:
        """Fetch the initial site and device lists (called once on first refresh)."""
        with _translate_errors():
            self._sites = await self._client.get_sites()
            self._devices = await self._client.get_devices()

            for site in self._sites:
                try:
                    detail = await self._client.get_site_detail(site.sid)
                except NepConnectionError, NepApiError:
                    _LOGGER.debug("Could not fetch site detail for %s", site.sid)
                else:
                    self._site_details[site.sid] = detail

    @override
    async def _async_update_data(self) -> NepViewerData:
        """Fetch current overview data for all sites and devices."""
        with _translate_errors():
            site_overviews = {
                site.sid: await self._client.get_site_overview(site.sid)
                for site in self._sites
            }
            device_overviews = {
                device.sn: await self._client.get_device_statistics_overview(device.sn)
                for device in self._devices
            }
            device_modules: dict[str, dict[str, Module]] = {}
            for site in self._sites:
                modules_data = await self._client.get_site_modules(site.sid)
                for device_entry in modules_data.devices:
                    device_modules[device_entry.sn] = {
                        module.plc_sn: module for module in device_entry.modules
                    }

        return NepViewerData(
            sites=self._sites,
            devices=self._devices,
            site_overviews=site_overviews,
            device_overviews=device_overviews,
            device_modules=device_modules,
            site_details=self._site_details,
        )

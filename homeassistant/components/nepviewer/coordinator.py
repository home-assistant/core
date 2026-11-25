"""DataUpdateCoordinator for the NEPViewer integration."""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
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
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

# Inverters normally report every few minutes, but gaps of an hour are common.
REPORT_TIMEOUT = timedelta(minutes=90)
# Inverters do not report at night, after a last report of 0 W.
IDLE_REPORT_TIMEOUT = timedelta(days=1)

type NepViewerConfigEntry = ConfigEntry[NepViewerCoordinator]


@dataclass(kw_only=True, slots=True)
class NepViewerData:
    """Data returned by a single coordinator refresh."""

    site_overviews: dict[str, SiteOverview]
    device_overviews: dict[str, DeviceStatisticsOverview]
    # Outer key: device sn. Inner key: module plc_sn.
    device_modules: dict[str, dict[str, Module]]


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
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self._client = client
        self.sites: list[Site] = []
        self.devices: list[Device] = []
        self.site_details: dict[str, SiteDetail] = {}
        self._time_zones: dict[str, tzinfo | None] = {}

    @override
    async def _async_setup(self) -> None:
        """Fetch the initial site and device lists (called once on first refresh)."""
        with _translate_errors():
            self.sites = await self._client.get_sites()
            self.devices = await self._client.get_devices()

            for site in self.sites:
                try:
                    detail = await self._client.get_site_detail(site.sid)
                except NepConnectionError, NepApiError:
                    _LOGGER.debug("Could not fetch site detail for %s", site.sid)
                else:
                    self.site_details[site.sid] = detail
                    self._time_zones[site.sid] = await dt_util.async_get_time_zone(
                        detail.timezone
                    )

    @override
    async def _async_update_data(self) -> NepViewerData:
        """Fetch current overview data for all sites and devices."""
        with _translate_errors():
            site_overviews = {
                site.sid: await self._client.get_site_overview(site.sid)
                for site in self.sites
            }
            device_overviews = {
                device.sn: await self._client.get_device_statistics_overview(device.sn)
                for device in self.devices
            }
            device_modules: dict[str, dict[str, Module]] = {}
            for site in self.sites:
                modules_data = await self._client.get_site_modules(site.sid)
                for device_entry in modules_data.devices:
                    device_modules[device_entry.sn] = {
                        module.plc_sn: module for module in device_entry.modules
                    }

        return NepViewerData(
            site_overviews=site_overviews,
            device_overviews=device_overviews,
            device_modules=device_modules,
        )

    def last_reported(self, device: Device) -> datetime | None:
        """Return when the device last reported to the cloud."""
        if (time_zone := self._time_zones.get(device.sid)) is None:
            return None
        return self.data.device_overviews[device.sn].last_update_datetime(time_zone)

    def is_device_reporting(self, device: Device) -> bool:
        """Return if the values of the device are recent enough to be trusted."""
        if (reported := self.last_reported(device)) is None:
            return True
        timeout = (
            REPORT_TIMEOUT
            if self.data.device_overviews[device.sn].total_now
            else IDLE_REPORT_TIMEOUT
        )
        return dt_util.utcnow() - reported <= timeout

    def is_site_reporting(self, sid: str) -> bool:
        """Return if any device of the site is reporting."""
        devices = [device for device in self.devices if device.sid == sid]
        return not devices or any(map(self.is_device_reporting, devices))

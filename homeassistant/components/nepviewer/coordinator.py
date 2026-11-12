"""DataUpdateCoordinator for the NEPViewer integration."""

from dataclasses import dataclass, field
from datetime import timedelta
import logging

from aionepviewer import NepApiError, NepAuthError, NepConnectionError, NepViewer
from aionepviewer.models.device import Device, DeviceStatisticsOverview
from aionepviewer.models.module import Module
from aionepviewer.models.site import Site, SiteDetail, SiteOverview

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


@dataclass
class NepViewerData:
    """Data returned by a single coordinator refresh."""

    sites: list[Site] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    site_overviews: dict[str, SiteOverview] = field(default_factory=dict)
    device_overviews: dict[str, DeviceStatisticsOverview] = field(default_factory=dict)
    # Outer key: device sn (uppercase). Inner key: module plc_sn.
    device_modules: dict[str, dict[str, Module]] = field(default_factory=dict)
    site_details: dict[str, SiteDetail] = field(default_factory=dict)


class NepViewerCoordinator(DataUpdateCoordinator[NepViewerData]):
    """Coordinator that polls the NEPViewer cloud API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
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

    async def _async_setup(self) -> None:
        """Fetch the initial site and device lists (called once on first refresh)."""
        try:
            self._sites = await self._client.get_sites()
            self._devices = await self._client.get_devices()
        except NepAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NepConnectionError as err:
            raise UpdateFailed(
                f"Error communicating with NEPViewer API: {err}"
            ) from err

        for site in self._sites:
            try:
                self._site_details[site.sid] = await self._client.get_site_detail(
                    site.sid
                )
            except NepConnectionError, NepApiError:
                _LOGGER.debug("Could not fetch site detail for %s", site.sid)

    async def _async_update_data(self) -> NepViewerData:
        """Fetch current overview data for all sites and devices."""
        try:
            site_overviews: dict[str, SiteOverview] = {}
            for site in self._sites:
                site_overviews[site.sid] = await self._client.get_site_overview(
                    site.sid
                )

            device_overviews: dict[str, DeviceStatisticsOverview] = {}
            for device in self._devices:
                device_overviews[
                    device.sn
                ] = await self._client.get_device_statistics_overview(device.sn)

            device_modules: dict[str, dict[str, Module]] = {}
            for site in self._sites:
                modules_data = await self._client.get_site_modules(site.sid)
                for device_entry in modules_data.devices:
                    device_modules[device_entry.sn.upper()] = {
                        m.plc_sn: m for m in device_entry.modules
                    }
        except NepAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NepConnectionError as err:
            raise UpdateFailed(
                f"Error communicating with NEPViewer API: {err}"
            ) from err

        return NepViewerData(
            sites=self._sites,
            devices=self._devices,
            site_overviews=site_overviews,
            device_overviews=device_overviews,
            device_modules=device_modules,
            site_details=self._site_details,
        )

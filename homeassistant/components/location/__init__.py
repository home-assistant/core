"""Location based discovery.

Starts discovery flows for integrations that serve the region of the home
location. Regions are stored as GeoJSON files in the regions directory and
integrations reference them by id with the locations key in their manifest.
"""

from collections import defaultdict
from collections.abc import Mapping
import logging
from pathlib import Path
from typing import Any

from homeassistant import config_entries
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.service_info.location import LocationServiceInfo
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_locations

from .const import DEFAULT_LOCATIONS, DOMAIN
from .region import available_regions, match_regions

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up location based discovery."""
    region_domains = await async_get_locations(hass)
    known_regions = await hass.async_add_executor_job(available_regions)
    for region_id in sorted(region_domains.keys() - known_regions.keys()):
        _LOGGER.warning(
            "Integrations %s use unknown region %s",
            ", ".join(region_domains[region_id]),
            region_id,
        )
    discovery = LocationDiscovery(
        hass,
        {
            region_id: domains
            for region_id, domains in region_domains.items()
            if region_id in known_regions
        },
        {
            region_id: path
            for region_id, path in known_regions.items()
            if region_id in region_domains
        },
    )

    async def _async_discover(hass: HomeAssistant) -> None:
        await discovery.async_discover()

    async_at_started(hass, _async_discover)
    hass.bus.async_listen(
        EVENT_CORE_CONFIG_UPDATE,
        discovery.async_core_config_updated,
        event_filter=_location_updated,
    )
    return True


@callback
def _location_updated(event_data: Mapping[str, Any]) -> bool:
    """Return if the core config update changed the home location."""
    return "latitude" in event_data or "longitude" in event_data


class LocationDiscovery:
    """Discover integrations serving the regions containing the home location."""

    def __init__(
        self,
        hass: HomeAssistant,
        region_domains: dict[str, list[str]],
        region_paths: dict[str, Path],
    ) -> None:
        """Initialize location discovery."""
        self.hass = hass
        self._region_domains = region_domains
        self._region_paths = region_paths
        self._location: tuple[float, float] | None = None

    async def async_core_config_updated(self, event: Event) -> None:
        """Handle the home location being updated."""
        await self.async_discover()

    async def async_discover(self) -> None:
        """Start discovery flows for the current home location."""
        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude
        if (latitude, longitude) == self._location:
            return
        self._location = (latitude, longitude)
        self._async_abort_stale_flows()

        if (latitude, longitude) in DEFAULT_LOCATIONS:
            return

        matched = await self.hass.async_add_executor_job(
            match_regions, self._region_paths, latitude, longitude
        )
        domain_regions: defaultdict[str, list[str]] = defaultdict(list)
        for region_id in sorted(matched):
            for domain in self._region_domains[region_id]:
                domain_regions[domain].append(region_id)

        for domain, regions in domain_regions.items():
            discovery_flow.async_create_flow(
                self.hass,
                domain,
                {"source": config_entries.SOURCE_LOCATION_DISCOVERY},
                LocationServiceInfo(
                    latitude=latitude, longitude=longitude, regions=regions
                ),
            )

    @callback
    def _async_abort_stale_flows(self) -> None:
        """Abort flows discovered for a previous home location."""
        flow_manager = self.hass.config_entries.flow
        for flow in flow_manager.async_progress_by_init_data_type(
            LocationServiceInfo,
            lambda info: (info.latitude, info.longitude) != self._location,
        ):
            flow_manager.async_abort(flow["flow_id"])

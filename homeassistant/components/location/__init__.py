"""Location based integration matching.

Finds the integrations that serve the region of the home location. Regions are
stored as GeoJSON files in the regions directory and integrations reference
them by id with the locations key in their manifest.
"""

from collections import defaultdict
import logging
from pathlib import Path
from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_locations
from homeassistant.util.hass_dict import HassKey

from .const import DEFAULT_LOCATIONS, DOMAIN
from .region import available_regions, match_regions

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

DATA_MATCHER: HassKey[LocationMatcher] = HassKey(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up location based integration matching."""
    region_domains = await async_get_locations(hass)
    known_regions = await hass.async_add_executor_job(available_regions)
    for region_id in sorted(region_domains.keys() - known_regions.keys()):
        _LOGGER.warning(
            "Integrations %s use unknown region %s",
            ", ".join(region_domains[region_id]),
            region_id,
        )
    hass.data[DATA_MATCHER] = LocationMatcher(
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
    websocket_api.async_register_command(hass, websocket_integrations)
    return True


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "location/integrations"})
@websocket_api.async_response
async def websocket_integrations(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the integrations serving the home location."""
    connection.send_result(
        msg["id"], await hass.data[DATA_MATCHER].async_get_integrations()
    )


class LocationMatcher:
    """Match the home location against the regions served by integrations."""

    def __init__(
        self,
        hass: HomeAssistant,
        region_domains: dict[str, list[str]],
        region_paths: dict[str, Path],
    ) -> None:
        """Initialize the location matcher."""
        self.hass = hass
        self._region_domains = region_domains
        self._region_paths = region_paths
        self._matched: tuple[tuple[float, float], set[str]] | None = None

    async def async_get_integrations(self) -> dict[str, list[str]]:
        """Return the integrations serving the home location.

        Maps each domain to the regions it serves that contain the home location.
        """
        location = (self.hass.config.latitude, self.hass.config.longitude)
        if location in DEFAULT_LOCATIONS:
            return {}

        if self._matched is None or self._matched[0] != location:
            self._matched = (
                location,
                await self.hass.async_add_executor_job(
                    match_regions, self._region_paths, *location
                ),
            )

        domain_regions: defaultdict[str, list[str]] = defaultdict(list)
        for region_id in sorted(self._matched[1]):
            for domain in self._region_domains[region_id]:
                domain_regions[domain].append(region_id)
        return dict(sorted(domain_regions.items()))

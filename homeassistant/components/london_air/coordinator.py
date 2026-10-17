"""The London Air data update coordinator."""

from collections import Counter
import logging
from typing import Any, override

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AUTHORITIES, DOMAIN, REQUEST_TIMEOUT, SCAN_INTERVAL, URL

_LOGGER = logging.getLogger(__name__)

type LondonAirConfigEntry = ConfigEntry[LondonAirDataUpdateCoordinator]

NO_SPECIES_DATA = "no_species_data"


class LondonAirDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]
):
    """Get the latest air quality data for all London authorities."""

    config_entry: LondonAirConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LondonAirConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._session = async_get_clientsession(hass)

    @override
    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch the latest data from the API."""
        try:
            response = await self._session.get(URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        return parse_api_response(payload)


def parse_api_response(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Parse the API payload into per-authority site data."""
    data: dict[str, list[dict[str, Any]]] = {authority: [] for authority in AUTHORITIES}
    for entry in payload["HourlyAirQualityIndex"]["LocalAuthority"]:
        authority = entry["@LocalAuthorityName"]
        if authority not in data:
            continue
        sites = entry.get("Site", [])
        if isinstance(sites, dict):
            sites = [sites]
        data[authority] = parse_sites(sites)
    return data


def parse_sites(sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse the monitoring sites for an authority."""
    return [parse_site(site) for site in sites]


def parse_site(site: dict[str, Any]) -> dict[str, Any]:
    """Parse a single monitoring site."""
    species = site.get("Species", [])
    if isinstance(species, dict):
        species = [species]
    pollutants, qualities = parse_species(species)
    return {
        "updated": site["@BulletinDate"],
        "latitude": site["@Latitude"],
        "longitude": site["@Longitude"],
        "site_code": site["@SiteCode"],
        "site_name": site["@SiteName"].split("-")[-1].lstrip(),
        "site_type": site["@SiteType"],
        "pollutants": pollutants,
        "pollutants_status": most_common(qualities) or NO_SPECIES_DATA,
        "number_of_pollutants": len(qualities),
    }


def parse_species(
    species: list[dict[str, Any]],
) -> tuple[list[dict[str, Any] | str], list[str]]:
    """Parse the pollutant species measured at a site."""
    pollutants: list[dict[str, Any] | str] = []
    qualities: list[str] = []
    for entry in species:
        quality = entry["@AirQualityBand"]
        if quality == "No data":
            continue
        code = entry["@SpeciesCode"]
        pollutants.append(
            {
                "description": entry["@SpeciesDescription"],
                "code": code,
                "quality": quality,
                "index": entry["@AirQualityIndex"],
                "summary": f"{code} is {quality}",
            }
        )
        qualities.append(quality)
    if not pollutants:
        # Preserve the legacy no-data sentinel for existing templates
        pollutants.append(NO_SPECIES_DATA)
    return pollutants, qualities


def most_common(values: list[str]) -> str | None:
    """Return the most common value, or None if the list is empty."""
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def authority_status(
    site_data: list[dict[str, Any]],
) -> str | None:
    """Return the dominant air quality band for an authority."""
    return most_common(
        [
            site["pollutants_status"]
            for site in site_data
            if site["pollutants_status"] != NO_SPECIES_DATA
        ]
    )

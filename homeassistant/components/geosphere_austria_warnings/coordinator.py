"""Data update coordinator for the GeoSphere Austria Warnings integration."""

from datetime import datetime, timedelta

from pygeosphere_warnings import (
    GeoSphereApiError,
    GeoSphereConnectionError,
    GeoSphereMunicipalityNotFoundError,
    GeoSphereWarningsClient,
    LocationWarnings,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

# Warnings are event driven and updated by GeoSphere Austria as needed.
# The cheap HEAD precheck keeps the cost of a poll low, so a relatively
# short interval is appropriate for timely warnings.
UPDATE_INTERVAL = timedelta(minutes=5)

type GeoSphereConfigEntry = ConfigEntry[GeoSphereUpdateCoordinator]


class GeoSphereUpdateCoordinator(DataUpdateCoordinator[LocationWarnings]):
    """Coordinator fetching warnings for a single municipality."""

    config_entry: GeoSphereConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: GeoSphereConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = GeoSphereWarningsClient(async_get_clientsession(hass))
        self._last_modified: datetime | None = None

    @property
    def _language(self) -> str:
        """Return the warning text language based on the user's language."""
        return "de" if self.hass.config.language.partition("-")[0] == "de" else "en"

    async def _async_update_data(self) -> LocationWarnings:
        """Fetch warnings, skipping the full fetch when nothing changed."""
        try:
            last_modified = await self.client.get_last_modified()
            if (
                self.data is None
                or last_modified is None
                or self._last_modified is None
                or last_modified > self._last_modified
            ):
                location_warnings = await self.client.get_warnings_for_coords(
                    self.config_entry.data[CONF_LATITUDE],
                    self.config_entry.data[CONF_LONGITUDE],
                    self._language,
                )
            else:
                location_warnings = self.data
        except GeoSphereMunicipalityNotFoundError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="municipality_not_found",
            ) from err
        except GeoSphereConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except GeoSphereApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err
        self._last_modified = last_modified
        return location_warnings

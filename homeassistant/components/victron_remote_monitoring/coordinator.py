"""VRM Coordinator and Client."""

from dataclasses import dataclass
import datetime

from victron_vrm import VictronVRMClient
from victron_vrm.exceptions import AuthenticationError, VictronVRMError
from victron_vrm.models.aggregations import ForecastAggregations
from victron_vrm.utils import dt_now

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_API_TOKEN, CONF_SITE_ID, DOMAIN, LOGGER

type VictronRemoteMonitoringConfigEntry = ConfigEntry[
    VictronRemoteMonitoringDataUpdateCoordinator
]


@dataclass
class VRMForecastStore:
    """Class to hold the forecast data."""

    site_id: int
    solar: ForecastAggregations | None
    consumption: ForecastAggregations | None


async def get_forecast(client: VictronVRMClient, site_id: int) -> VRMForecastStore:
    """Get the forecast data."""
    start = int(
        (
            dt_now().replace(hour=0, minute=0, second=0, microsecond=0)
            - datetime.timedelta(days=1)
        ).timestamp()
    )
    # Get timestamp of the end of 6th day from now
    end = int(
        (
            dt_now().replace(hour=0, minute=0, second=0, microsecond=0)
            + datetime.timedelta(days=6)
        ).timestamp()
    )
    stats = await client.installations.stats(
        site_id,
        start=start,
        end=end,
        interval="hours",
        type="forecast",
        return_aggregations=True,
    )
    return VRMForecastStore(
        solar=stats["solar_yield"],
        consumption=stats["consumption"],
        site_id=site_id,
    )


class VictronRemoteMonitoringDataUpdateCoordinator(
    DataUpdateCoordinator[VRMForecastStore]
):
    """Class to manage fetching VRM Forecast data."""

    config_entry: VictronRemoteMonitoringConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: VictronRemoteMonitoringConfigEntry,
    ) -> None:
        """Initialize."""
        self.client = VictronVRMClient(
            token=config_entry.data[CONF_API_TOKEN],
            client_session=async_get_clientsession(hass),
        )
        self.site_id = config_entry.data[CONF_SITE_ID]
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=datetime.timedelta(minutes=60),
        )

    async def _async_update_data(self) -> VRMForecastStore:
        """Fetch data from VRM API."""
        try:
            return await get_forecast(self.client, self.site_id)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Invalid authentication for VRM API: {err}"
            ) from err
        except VictronVRMError as err:
            raise UpdateFailed(f"Cannot connect to VRM API: {err}") from err

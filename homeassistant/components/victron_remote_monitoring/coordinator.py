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

from .const import (
    CONF_API_TOKEN,
    CONF_MQTT_UPDATE_FREQUENCY_SECONDS,
    CONF_SITE_ID,
    DEFAULT_MQTT_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
    LOGGER,
)
from .mqtt_hub import VRMMqttHub

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
        self.mqtt_client = None
        self.mqtt_hub = VRMMqttHub(self.site_id)
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

    async def start_mqtt(self) -> None:
        """Start the MQTT client."""
        if self.mqtt_client is not None:
            LOGGER.debug("MQTT client already started")
            return  # Already started
        update_frequency = self.config_entry.options.get(
            CONF_MQTT_UPDATE_FREQUENCY_SECONDS,
            DEFAULT_MQTT_UPDATE_FREQUENCY_SECONDS,
        )
        mqtt_client = await self.client.get_mqtt_client_for_installation(
            self.site_id, update_frequency=update_frequency
        )
        self.mqtt_client = mqtt_client
        try:
            self.mqtt_hub.attach(mqtt_client)
            await mqtt_client.connect()
            LOGGER.debug("MQTT client connected")
        except (TimeoutError, OSError, RuntimeError, VictronVRMError) as ex:
            self.mqtt_hub.detach()
            self.mqtt_client = None
            LOGGER.error("Failed to connect MQTT client: %s", ex)
            raise

    async def stop_mqtt(self) -> None:
        """Stop the MQTT client."""
        if self.mqtt_client is None:
            LOGGER.debug("MQTT client not started")
            return  # Not started
        try:
            await self.mqtt_client.disconnect()
            LOGGER.debug("MQTT client disconnected")
        except (TimeoutError, OSError, RuntimeError, VictronVRMError) as ex:
            LOGGER.error("Failed to disconnect MQTT client: %s", ex)
            raise
        finally:
            self.mqtt_hub.detach()
            self.mqtt_client = None

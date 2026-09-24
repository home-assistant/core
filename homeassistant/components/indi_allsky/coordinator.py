"""DataUpdateCoordinator for INDI Allsky integration."""

from dataclasses import dataclass
import logging
from typing import override

from aioindiallsky import ExposureData, IndiAllSkyClient, IndiAllSkyError, SensorData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import get_ssl_context

_LOGGER = logging.getLogger(__name__)

type IndiAllSkyConfigEntry = ConfigEntry[IndiAllSkyDataUpdateCoordinator]


@dataclass
class IndiAllSkyData:
    """Data model for INDI Allsky coordinator data."""

    exposure: ExposureData | None = None
    sensor: SensorData | None = None


class IndiAllSkyDataUpdateCoordinator(DataUpdateCoordinator[IndiAllSkyData]):
    """Class to manage fetching INDI Allsky data from the API."""

    def __init__(self, hass: HomeAssistant, entry: IndiAllSkyConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = IndiAllSkyClient(
            host=entry.data[CONF_HOST],
            port=int(entry.data[CONF_PORT]),
            ssl=get_ssl_context(
                entry.data[CONF_SSL],
                entry.data[CONF_VERIFY_SSL],
            ),
            session=async_get_clientsession(hass),
        )
        self.latest_exposure: ExposureData | None = None
        self.latest_sensor: SensorData | None = None

        unsub_exp = self.client.register_callback(
            "exposure_complete", self._handle_exposure_complete
        )
        unsub_sensor = self.client.register_callback(
            "sensor_update", self._handle_sensor_update
        )
        entry.async_on_unload(unsub_exp)
        entry.async_on_unload(unsub_sensor)
        entry.async_on_unload(self.client.disconnect)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )

    def _handle_exposure_complete(self, exposure: ExposureData) -> None:
        """Handle new exposure_complete event from WebSocket stream."""
        self.latest_exposure = exposure
        self.async_set_updated_data(
            IndiAllSkyData(
                exposure=exposure,
                sensor=self.latest_sensor,
            )
        )

    def _handle_sensor_update(self, sensor: SensorData) -> None:
        """Handle new sensor_update event from WebSocket stream."""
        if self.latest_sensor is not None:
            merged_sensors = dict(self.latest_sensor.sensors)
            merged_sensors.update(sensor.sensors)

            merged_temp = (
                list(sensor.raw_temp)
                if sensor.raw_temp
                else list(self.latest_sensor.raw_temp)
            )
            merged_user = (
                list(sensor.raw_user)
                if sensor.raw_user
                else list(self.latest_sensor.raw_user)
            )

            merged_data = dict(self.latest_sensor.raw_data or {})
            if sensor.raw_data:
                merged_data.update(sensor.raw_data)

            self.latest_sensor = SensorData(
                last_update=sensor.last_update or self.latest_sensor.last_update,
                sensors=merged_sensors,
                raw_temp=merged_temp,
                raw_user=merged_user,
                raw_data=merged_data,
                dew_heater=sensor.dew_heater
                if sensor.dew_heater is not None
                else self.latest_sensor.dew_heater,
                dew_point=sensor.dew_point
                if sensor.dew_point is not None
                else self.latest_sensor.dew_point,
                frost_point=sensor.frost_point
                if sensor.frost_point is not None
                else self.latest_sensor.frost_point,
                fan_duty_cycle=sensor.fan_duty_cycle
                if sensor.fan_duty_cycle is not None
                else self.latest_sensor.fan_duty_cycle,
                heat_index=sensor.heat_index
                if sensor.heat_index is not None
                else self.latest_sensor.heat_index,
                wind_direction=sensor.wind_direction
                if sensor.wind_direction is not None
                else self.latest_sensor.wind_direction,
                device_sqm=sensor.device_sqm
                if sensor.device_sqm is not None
                else self.latest_sensor.device_sqm,
                camera_sqm=sensor.camera_sqm
                if sensor.camera_sqm is not None
                else self.latest_sensor.camera_sqm,
                camera_sqm_adu=sensor.camera_sqm_adu
                if sensor.camera_sqm_adu is not None
                else self.latest_sensor.camera_sqm_adu,
                cpu_temperature=sensor.cpu_temperature
                if sensor.cpu_temperature is not None
                else self.latest_sensor.cpu_temperature,
            )
        else:
            self.latest_sensor = sensor

        self.async_set_updated_data(
            IndiAllSkyData(
                exposure=self.latest_exposure,
                sensor=self.latest_sensor,
            )
        )

    @override
    async def _async_update_data(self) -> IndiAllSkyData:
        """Fetch INDI Allsky metadata and verify connection."""
        try:
            await self.client.fetch_image("latestimage")
            if not self.client.is_connected:
                await self.client.connect()
            if self.latest_sensor is None:
                await self.client.fetch_sensors()
        except IndiAllSkyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

        return IndiAllSkyData(
            exposure=self.latest_exposure,
            sensor=self.latest_sensor,
        )

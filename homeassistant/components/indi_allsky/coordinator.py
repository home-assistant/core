"""DataUpdateCoordinator for INDI Allsky integration."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from aioindiallsky import (
    ExposureData,
    IndiAllSkyAuthError,
    IndiAllSkyClient,
    IndiAllSkyError,
    MediaData,
    SensorData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .util import get_ssl_context

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=10)

type IndiAllSkyConfigEntry = ConfigEntry[IndiAllSkyDataUpdateCoordinator]


@dataclass
class IndiAllSkyData:
    """Data model for INDI Allsky coordinator data."""

    exposure: ExposureData | None = None
    latest_keogram: MediaData | None = None
    latest_keogram_image: bytes | None = None
    latest_keogram_updated: datetime | None = None
    latest_startrail: MediaData | None = None
    latest_startrail_image: bytes | None = None
    latest_startrail_updated: datetime | None = None
    sensor: SensorData | None = None


class IndiAllSkyDataUpdateCoordinator(DataUpdateCoordinator[IndiAllSkyData]):
    """Class to manage fetching INDI Allsky data from the API."""

    config_entry: IndiAllSkyConfigEntry

    def __init__(self, hass: HomeAssistant, entry: IndiAllSkyConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = IndiAllSkyClient(
            host=entry.data[CONF_HOST],
            port=int(entry.data[CONF_PORT]),
            ssl=get_ssl_context(
                entry.data[CONF_SSL],
                entry.data[CONF_VERIFY_SSL],
            ),
            username=entry.data.get(CONF_USERNAME),
            password=entry.data.get(CONF_PASSWORD),
            session=async_get_clientsession(hass),
        )
        self.latest_exposure: ExposureData | None = None
        self.latest_keogram: MediaData | None = None
        self.latest_keogram_image: bytes | None = None
        self.latest_keogram_updated: datetime | None = None
        self.latest_startrail: MediaData | None = None
        self.latest_startrail_image: bytes | None = None
        self.latest_startrail_updated: datetime | None = None
        self.latest_sensor: SensorData | None = None
        self._sensor_fetch_task: asyncio.Task[None] | None = None
        self._sensor_fetch_queued = False

        entry.async_on_unload(
            self.client.register_callback(
                "exposure_complete", self._handle_exposure_complete
            )
        )
        entry.async_on_unload(
            self.client.register_callback(
                "keogram_complete", self._handle_keogram_complete
            )
        )
        entry.async_on_unload(
            self.client.register_callback(
                "startrail_complete", self._handle_startrail_complete
            )
        )
        entry.async_on_unload(
            self.client.register_callback("sensor_update", self._handle_sensor_update)
        )
        entry.async_on_unload(self.client.disconnect)
        if not entry.pref_disable_polling:
            entry.async_on_unload(
                async_track_time_interval(
                    hass,
                    self._async_handle_interval_refresh,
                    SCAN_INTERVAL,
                )
            )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )

    async def _async_handle_interval_refresh(self, _now: datetime) -> None:
        """Handle periodic fallback sensor polling."""
        self._async_trigger_fetch_sensors()

    def _handle_exposure_complete(self, exposure: ExposureData) -> None:
        """Handle new exposure_complete event from WebSocket stream."""
        self.latest_exposure = exposure
        self._async_trigger_fetch_sensors()
        self.async_set_updated_data(
            IndiAllSkyData(
                exposure=exposure,
                latest_keogram=self.latest_keogram,
                latest_keogram_image=self.latest_keogram_image,
                latest_keogram_updated=self.latest_keogram_updated,
                latest_startrail=self.latest_startrail,
                latest_startrail_image=self.latest_startrail_image,
                latest_startrail_updated=self.latest_startrail_updated,
                sensor=self.latest_sensor,
            )
        )

    def _async_trigger_fetch_sensors(self) -> None:
        """Trigger sensor fetch if no fetch task is active, or queue a trailing run."""
        if self._sensor_fetch_task is not None and not self._sensor_fetch_task.done():
            self._sensor_fetch_queued = True
            return
        self._sensor_fetch_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_fetch_sensors(),
            "indi_allsky_fetch_sensors",
        )

    async def _async_fetch_sensors(self) -> None:
        """Fetch sensor update from indi-allsky, processing any queued trailing fetch."""
        while True:
            self._sensor_fetch_queued = False
            try:
                try:
                    await self.client.fetch_sensors()
                except IndiAllSkyAuthError:
                    self.config_entry.async_start_reauth(self.hass)
                except IndiAllSkyError:
                    pass
            finally:
                if not self._sensor_fetch_queued:
                    self._sensor_fetch_task = None
            if not self._sensor_fetch_queued:
                break

    def _handle_keogram_complete(self, media: MediaData) -> None:
        """Handle new keogram_complete event from WebSocket stream."""
        self.latest_keogram = media
        self.latest_keogram_image = None
        self.latest_keogram_updated = None
        self.config_entry.async_create_background_task(
            self.hass,
            self._async_fetch_keogram_and_update(media),
            "indi_allsky_fetch_keogram",
        )

    @callback
    def async_set_keogram_image(
        self, media: MediaData, image_bytes: bytes | None
    ) -> None:
        """Update cached keogram image if media matches current."""
        if media is not self.latest_keogram:
            return
        if image_bytes is None and self.latest_keogram_image is not None:
            return
        self.latest_keogram_image = image_bytes
        self.latest_keogram_updated = (
            dt_util.utcnow() if image_bytes is not None else None
        )
        self.async_set_updated_data(
            IndiAllSkyData(
                exposure=self.latest_exposure,
                latest_keogram=self.latest_keogram,
                latest_keogram_image=self.latest_keogram_image,
                latest_keogram_updated=self.latest_keogram_updated,
                latest_startrail=self.latest_startrail,
                latest_startrail_image=self.latest_startrail_image,
                latest_startrail_updated=self.latest_startrail_updated,
                sensor=self.latest_sensor,
            )
        )

    async def _async_fetch_keogram_and_update(self, media: MediaData) -> None:
        """Fetch latest keogram image and update coordinator."""
        image_bytes: bytes | None
        try:
            image_bytes = await self.client.fetch_image("latestkeogram")
        except IndiAllSkyAuthError:
            self.config_entry.async_start_reauth(self.hass)
            image_bytes = None
        except IndiAllSkyError as err:
            _LOGGER.warning("Failed to fetch latest keogram image: %s", err)
            image_bytes = None
        self.async_set_keogram_image(media, image_bytes)

    def _handle_startrail_complete(self, media: MediaData) -> None:
        """Handle new startrail_complete event from WebSocket stream."""
        self.latest_startrail = media
        self.latest_startrail_image = None
        self.latest_startrail_updated = None
        self.config_entry.async_create_background_task(
            self.hass,
            self._async_fetch_startrail_and_update(media),
            "indi_allsky_fetch_startrail",
        )

    @callback
    def async_set_startrail_image(
        self, media: MediaData, image_bytes: bytes | None
    ) -> None:
        """Update cached startrail image if media matches current."""
        if media is not self.latest_startrail:
            return
        if image_bytes is None and self.latest_startrail_image is not None:
            return
        self.latest_startrail_image = image_bytes
        self.latest_startrail_updated = (
            dt_util.utcnow() if image_bytes is not None else None
        )
        self.async_set_updated_data(
            IndiAllSkyData(
                exposure=self.latest_exposure,
                latest_keogram=self.latest_keogram,
                latest_keogram_image=self.latest_keogram_image,
                latest_keogram_updated=self.latest_keogram_updated,
                latest_startrail=self.latest_startrail,
                latest_startrail_image=self.latest_startrail_image,
                latest_startrail_updated=self.latest_startrail_updated,
                sensor=self.latest_sensor,
            )
        )

    async def _async_fetch_startrail_and_update(self, media: MediaData) -> None:
        """Fetch latest startrail image and update coordinator."""
        image_bytes: bytes | None
        try:
            image_bytes = await self.client.fetch_image("lateststartrail")
        except IndiAllSkyAuthError:
            self.config_entry.async_start_reauth(self.hass)
            image_bytes = None
        except IndiAllSkyError as err:
            _LOGGER.warning("Failed to fetch latest startrail image: %s", err)
            image_bytes = None
        self.async_set_startrail_image(media, image_bytes)

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
                latest_keogram=self.latest_keogram,
                latest_keogram_image=self.latest_keogram_image,
                latest_keogram_updated=self.latest_keogram_updated,
                latest_startrail=self.latest_startrail,
                latest_startrail_image=self.latest_startrail_image,
                latest_startrail_updated=self.latest_startrail_updated,
                sensor=self.latest_sensor,
            )
        )

    @override
    async def _async_update_data(self) -> IndiAllSkyData:
        """Fetch INDI Allsky metadata and verify connection."""
        try:
            if self.latest_exposure is None:
                await self.client.fetch_image("latestimage")
            if not self.client.is_connected:
                await self.client.connect()
            await self.client.fetch_sensors()
        except IndiAllSkyAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except IndiAllSkyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

        return IndiAllSkyData(
            exposure=self.latest_exposure,
            latest_keogram=self.latest_keogram,
            latest_keogram_image=self.latest_keogram_image,
            latest_keogram_updated=self.latest_keogram_updated,
            latest_startrail=self.latest_startrail,
            latest_startrail_image=self.latest_startrail_image,
            latest_startrail_updated=self.latest_startrail_updated,
            sensor=self.latest_sensor,
        )

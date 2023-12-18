"""Support for SimpliSafe binary sensors."""
from __future__ import annotations

import asyncio
from datetime import datetime
import os
import pathlib

from simplipy.device import DeviceTypes, DeviceV3
from simplipy.device.sensor.v3 import SensorV3
from simplipy.errors import SimplipyError
from simplipy.system.v3 import SystemV3
from simplipy.util.dt import utc_from_timestamp
from simplipy.websocket import EVENT_CAMERA_MOTION_DETECTED, WebsocketEvent

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SimpliSafe, SimpliSafeEntity
from .const import DOMAIN, LOGGER

DEFAULT_IMAGE_WIDTH = 720

SUPPORTED_BATTERY_SENSOR_TYPES = [
    DeviceTypes.CARBON_MONOXIDE,
    DeviceTypes.DOORBELL,
    DeviceTypes.ENTRY,
    DeviceTypes.GLASS_BREAK,
    DeviceTypes.KEYCHAIN,
    DeviceTypes.KEYPAD,
    DeviceTypes.LEAK,
    DeviceTypes.LOCK,
    DeviceTypes.LOCK_KEYPAD,
    DeviceTypes.MOTION,
    DeviceTypes.MOTION_V2,
    DeviceTypes.PANIC_BUTTON,
    DeviceTypes.REMOTE,
    DeviceTypes.SIREN,
    DeviceTypes.SMOKE,
    DeviceTypes.SMOKE_AND_CARBON_MONOXIDE,
    DeviceTypes.TEMPERATURE,
    DeviceTypes.OUTDOOR_CAMERA,
]

TRIGGERED_SENSOR_TYPES = {
    DeviceTypes.CARBON_MONOXIDE: BinarySensorDeviceClass.GAS,
    DeviceTypes.ENTRY: BinarySensorDeviceClass.DOOR,
    DeviceTypes.GLASS_BREAK: BinarySensorDeviceClass.SAFETY,
    DeviceTypes.LEAK: BinarySensorDeviceClass.MOISTURE,
    DeviceTypes.MOTION: BinarySensorDeviceClass.MOTION,
    DeviceTypes.MOTION_V2: BinarySensorDeviceClass.MOTION,
    DeviceTypes.SIREN: BinarySensorDeviceClass.SAFETY,
    DeviceTypes.SMOKE: BinarySensorDeviceClass.SMOKE,
    # Although this sensor can technically apply to both smoke and carbon, we use the
    # SMOKE device class for simplicity:
    DeviceTypes.SMOKE_AND_CARBON_MONOXIDE: BinarySensorDeviceClass.SMOKE,
}

OUTDOOR_CAMERA_SENSOR_TYPES = {
    DeviceTypes.OUTDOOR_CAMERA: BinarySensorDeviceClass.MOTION,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SimpliSafe binary sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id]

    sensors: list[
        BatteryBinarySensor | TriggeredBinarySensor | OutdoorCameraSensor
    ] = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping sensor setup for V2 system: %s", system.system_id)
            continue

        for sensor in system.sensors.values():
            if sensor.type in TRIGGERED_SENSOR_TYPES:
                sensors.append(
                    TriggeredBinarySensor(
                        simplisafe,
                        system,
                        sensor,
                        TRIGGERED_SENSOR_TYPES[sensor.type],
                    )
                )
            if sensor.type in OUTDOOR_CAMERA_SENSOR_TYPES:
                sensors.append(
                    OutdoorCameraSensor(
                        hass,
                        simplisafe,
                        system,
                        sensor,
                        OUTDOOR_CAMERA_SENSOR_TYPES[sensor.type],
                    )
                )
            if sensor.type in SUPPORTED_BATTERY_SENSOR_TYPES:
                sensors.append(BatteryBinarySensor(simplisafe, system, sensor))

        for lock in system.locks.values():
            sensors.append(BatteryBinarySensor(simplisafe, system, lock))

    async_add_entities(sensors)


class TriggeredBinarySensor(SimpliSafeEntity, BinarySensorEntity):
    """Define a binary sensor related to whether an entity has been triggered."""

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemV3,
        sensor: SensorV3,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize."""
        super().__init__(simplisafe, system, device=sensor)

        self._attr_device_class = device_class
        self._device: SensorV3

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_is_on = self._device.triggered


class BatteryBinarySensor(SimpliSafeEntity, BinarySensorEntity):
    """Define a SimpliSafe battery binary sensor entity."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, simplisafe: SimpliSafe, system: SystemV3, device: DeviceV3
    ) -> None:
        """Initialize."""
        super().__init__(simplisafe, system, device=device)

        self._attr_unique_id = f"{super().unique_id}-battery"
        self._device: DeviceV3

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_is_on = self._device.low_battery


class OutdoorCameraSensor(SimpliSafeEntity, BinarySensorEntity):
    """Define a binary sensor for the outdoor camera.

    The Simplisafe Outdoor camera is a motion based device that captures an image and
    a short video clip when motion is detected.  When motion is detected, an event is
    sent over the Simplisafe websocket, consumed by the Simplisafe class and forwarded to
    this entity.  We then save clips and videos (mp4) into the local file system using this
    structure:

    /config/www/simplisafe/{outdoor_camera_name}/
      latest_snapshot.jpg
      latest_clip.mp4
      clips/
        YYYYMMDDHHmmss.mp4
        ...

    You can use a Gallery Card (https://github.com/TarheelGrad1998/gallery-card) pointed at
    the clips/ directory, and use the latest_* files in automations if you want.
    """

    # Properties
    _attr_image_last_updated: datetime | None = None
    _attr_image_url: str | None = None
    _attr_clip_url: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        simplisafe: SimpliSafe,
        system: SystemV3,
        sensor: SensorV3,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize."""
        super().__init__(
            simplisafe,
            system,
            device=sensor,
            additional_websocket_events=[EVENT_CAMERA_MOTION_DETECTED],
        )

        self._attr_device_class = device_class
        # self._attr_unique_id = f"{super().unique_id}-motion-camera"
        self._device: SensorV3
        self._attr_is_on = False

        # make the directories for storing media
        self.storage = pathlib.Path(
            os.path.join(
                hass.config.path("www"),
                DOMAIN,
                sensor.name.lower().replace(" ", "_"),
            )
        )
        self.storage.mkdir(parents=True, exist_ok=True)
        clips = pathlib.Path(os.path.join(self.storage, "clips"))
        clips.mkdir(parents=True, exist_ok=True)

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Receive a Simplisafe WebsocketEvent aimed at me specifically."""
        if event.event_type != EVENT_CAMERA_MOTION_DETECTED:
            return
        if event.sensor_type != DeviceTypes.OUTDOOR_CAMERA:
            return

        LOGGER.debug(
            "Outdoor Camera %s received a websocket event: %s",
            self._device.serial,
            event,
        )

        if not hasattr(event, "mediaUrls"):
            # Used when simplipy version is 2023.08.0 and below
            self.hass.async_create_task(
                self._async_update_camera_media_the_old_way(event.timestamp)
            )
            return
        if event.mediaUrls is not None:
            # Used when simplipy version is greater 2023.08.0 (or when the "mediaUrls" pull request was approved)
            imageUrl = event.mediaUrls["snapshot/jpg"]["href"]
            clipUrl = event.mediaUrls["download/mp4"]["href"]
            timestamp = event.timestamp
            if timestamp != self._attr_image_last_updated:
                self._attr_image_url = imageUrl
                self._attr_clip_url = clipUrl
                self._attr_is_on = True
                self._attr_image_last_updated = timestamp
                self.hass.async_create_task(self._async_update_camera_media())

    async def _async_get_media_content(self, url: str) -> bytes | None:
        """Get a media file from a URL.

        When Simplisafe sends the websocket event containing urls to media files, IT
        HAS APPARENTLY NOT yet written those files ... or at least those files are not yet
        available to fetch (maybe they are still sneaking through AWS).  We'll get a 404
        for these ... so we need to loop trying to get them, doing a small backoff in between,
        and giving up after some reasonable number of attempts.  Nothing's easy.
        """
        LOGGER.debug("Outdoor Camera fetching media from %s", url)
        # I need access to the Authorization header (access_token) to call these media endpoints,
        # as they are not known in simplipy!
        # pylint: disable=protected-access
        api = self._simplisafe._api
        access_token = api.access_token
        session = api.session

        # For me, the number of tries seems about 3-5, but just to be safe ...
        tries = 30
        tried = 0

        payload = None

        while True:
            response = await session.request(
                "get", url, headers={"Authorization": f"Bearer {access_token}"}
            )
            LOGGER.debug("Outdoor Camera fetch response status: %s", response.status)
            if response.status == 200:
                payload = response
                break
            if tried == tries:
                break
            tried = tried + 1
            await asyncio.sleep(1)
            LOGGER.debug("Outdoor Camera fetch retry %s", tried)

        if payload is not None:
            return await payload.read()
        return None

    async def _async_get_image_content(
        self, url, width: int = DEFAULT_IMAGE_WIDTH
    ) -> bytes | None:
        return await self._async_get_media_content(
            url.replace("{&width}", "&width=" + str(width))
        )

    async def _async_update_camera_media_the_old_way(
        self, ws_timestamp: datetime
    ) -> None:
        """Obtain media URLs by fetching timeline from Simplisafe API.

        The simplipy library <= 2023.08.0 does not transmit "mediaUrls" property in websocket events.
        The only way to obtain media urls is to get the event "timeline" and parse that ...
        """
        try:
            events = await self._system.async_get_events(num_events=10)
            # filter for events belonging to me at the websocket timestamp
            my_events = [
                ev
                for ev in events
                if ev.get("sensorSerial") == self._device.serial
                and ws_timestamp == utc_from_timestamp(ev["eventTimestamp"])
            ]
            if len(my_events) == 0:
                LOGGER.error(
                    "Could not find an event for serial: %s at time: %s",
                    self._device.serial,
                    ws_timestamp,
                )
                LOGGER.debug("Here are the events fetched: %s", events)
                return

            ev = my_events[0]
            vid = ev["videoStartedBy"]
            # This happends sometimes ...
            if vid == "":
                LOGGER.warning(
                    "Received a motion event for serial %s, but videoStartedBy key is empty!",
                    self._device.serial,
                )
                LOGGER.warning("Here are the events fetched: %s", events)
                return

            urls = ev["video"][vid]["_links"]
            imageUrl = urls["snapshot/jpg"]["href"]
            clipUrl = urls["download/mp4"]["href"]
            timestamp = utc_from_timestamp(ev["eventTimestamp"])

            if timestamp != self._attr_image_last_updated:
                self._attr_image_url = imageUrl
                self._attr_clip_url = clipUrl
                self._attr_is_on = True
                self._attr_image_last_updated = timestamp
                self.async_write_ha_state()
                await self._async_update_camera_media()

        except SimplipyError as err:
            LOGGER.error("Error while fetching most recent image: %s", err)

    async def _save_media_file(
        self, hass: HomeAssistant, filename: str, content: bytes
    ) -> None:
        if content is None:
            return

        def save_file() -> None:
            with open(filename, "wb") as fh:
                fh.write(content)

        try:
            await hass.async_add_executor_job(save_file)
        except OSError as err:
            LOGGER.error("Can't write %s: %s", filename, err)

    async def _async_get_and_store_media(
        self, width: int | None = DEFAULT_IMAGE_WIDTH, height: int | None = None
    ) -> bytes | None:
        local_timestamp = dt_util.as_local(self._attr_image_last_updated)
        datestr = local_timestamp.strftime("%Y%m%d%H%M%S")
        start = datetime.now()

        if self._attr_image_url is not None:
            image_data = await self._async_get_image_content(
                self._attr_image_url, width
            )

            await self._save_media_file(
                self.hass, os.path.join(self.storage, "latest_snapshot.jpg"), image_data
            )

        if self._attr_clip_url is not None:
            clip_data = await self._async_get_media_content(self._attr_clip_url)

            await self._save_media_file(
                self.hass, os.path.join(self.storage, "latest_clip.mp4"), clip_data
            )

            await self._save_media_file(
                self.hass,
                os.path.join(self.storage, "clips", datestr + ".mp4"),
                clip_data,
            )

            delta = datetime.now() - start

        LOGGER.debug(
            "Outdoor Camera media fetch and save took %s seconds", delta.seconds
        )

        return None

    async def _async_update_camera_media(self):
        await self._async_get_and_store_media()
        self._attr_is_on = False
        self.async_write_ha_state()

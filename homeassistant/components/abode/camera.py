"""Support for Abode Security System cameras."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from jaraco.abode.devices.base import Device
from jaraco.abode.devices.camera import Camera as AbodeCam
from jaraco.abode.helpers import timeline
from jaraco.abode.helpers.constants import TYPE_CAMERA
import requests
from requests.models import Response

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import AbodeDevice, AbodeSystem
from .const import DOMAIN, LOGGER

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=90)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Abode camera devices."""
    data: AbodeSystem = hass.data[DOMAIN]

    async_add_entities(
        AbodeCamera(data, device, timeline.CAPTURE_IMAGE)
        for device in data.abode.get_devices(generic_type=TYPE_CAMERA)
    )


class AbodeCamera(AbodeDevice, Camera):
    """Representation of an Abode camera."""

    _device: AbodeCam
    _attr_name = None

    def __init__(self, data: AbodeSystem, device: Device, event: Event) -> None:
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, data, device)
        Camera.__init__(self)
        self._event = event
        self._response: Response | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe Abode events."""
        await super().async_added_to_hass()

        self.hass.async_add_executor_job(
            self._data.abode.events.add_timeline_callback,
            self._event,
            self._capture_callback,
        )

        signal = f"abode_camera_capture_{self.entity_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self.capture))

    def capture(self) -> bool:
        """Request a new image capture."""
        return cast(bool, self._device.capture())

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_image(self) -> None:
        """Find a new image on the timeline."""
        if self._device.refresh_image():
            self.get_image()

    def get_image(self) -> None:
        """Attempt to download the most recent capture."""
        if self._device.image_url:
            try:
                self._response = requests.get(
                    self._device.image_url, stream=True, timeout=10
                )

                self._response.raise_for_status()
            except requests.HTTPError as err:
                LOGGER.warning("Failed to get camera image: %s", err)
                self._response = None
        else:
            self._response = None

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Get a camera image."""
        self.refresh_image()

        if self._response:
            return self._response.content

        return None

    def turn_on(self) -> None:
        """Turn on camera."""
        self._device.privacy_mode(False)

    def turn_off(self) -> None:
        """Turn off camera."""
        self._device.privacy_mode(True)

    def _capture_callback(self, capture: Any) -> None:
        """Update the image with the device then refresh device."""
        self._device.update_image_location(capture)
        self.get_image()
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return cast(bool, self._device.is_on)

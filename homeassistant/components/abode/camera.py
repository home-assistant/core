"""Support for Abode Security System cameras."""

from collections.abc import Callable
from datetime import timedelta
from functools import partial
from typing import Any, cast, override

from jaraco.abode.devices.base import Device
from jaraco.abode.devices.camera import Camera as AbodeCam
from jaraco.abode.helpers import timeline
import requests
from requests.models import Response

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import Throttle

from . import AbodeConfigEntry, AbodeSystem
from .const import LOGGER
from .entity import AbodeDevice

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=90)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbodeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Abode camera devices."""
    data = entry.runtime_data

    # jaraco.abode can't remove timeline callbacks, so register one per entry
    # and let cameras subscribe and unsubscribe through the dispatcher.
    signal = f"abode_camera_timeline_capture_{entry.entry_id}"
    await hass.async_add_executor_job(
        data.abode.events.add_timeline_callback,
        timeline.CAPTURE_IMAGE,
        partial(dispatcher_send, hass, signal),
    )

    async_add_entities(
        AbodeCamera(data, device, signal)
        for device in data.abode.get_devices(generic_type="camera")
    )


class AbodeCamera(AbodeDevice, Camera):
    """Representation of an Abode camera."""

    _device: AbodeCam
    _attr_name = None
    _unsub_capture_signal: Callable[[], None]

    def __init__(self, data: AbodeSystem, device: Device, timeline_signal: str) -> None:
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, data, device)
        Camera.__init__(self)
        self._timeline_signal = timeline_signal
        self._response: Response | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe Abode events."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._timeline_signal, self._capture_callback
            )
        )

        self._async_connect_capture_signal()
        # The lambda is needed because _unsub_capture_signal is reassigned
        # on entity id change.
        # pylint: disable-next=unnecessary-lambda
        self.async_on_remove(lambda: self._unsub_capture_signal())

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Reconnect the capture signal, which is keyed on the entity_id."""
        super().async_entity_id_changed(old_entity_id)
        self._unsub_capture_signal()
        self._async_connect_capture_signal()

    @callback
    def _async_connect_capture_signal(self) -> None:
        """Connect the capture signal for the current entity_id."""
        self._unsub_capture_signal = async_dispatcher_connect(
            self.hass, f"abode_camera_capture_{self.entity_id}", self.capture
        )

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

    @override
    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Get a camera image."""
        self.refresh_image()

        if self._response:
            return self._response.content

        return None

    @override
    def turn_on(self) -> None:
        """Turn on camera."""
        self._device.privacy_mode(False)

    @override
    def turn_off(self) -> None:
        """Turn off camera."""
        self._device.privacy_mode(True)

    def _capture_callback(self, capture: Any) -> None:
        """Update the image with the device then refresh device."""
        self._device.update_image_location(capture)
        self.get_image()
        self.schedule_update_ha_state()

    @property
    @override
    def is_on(self) -> bool:
        """Return true if on."""
        return cast(bool, self._device.is_on)

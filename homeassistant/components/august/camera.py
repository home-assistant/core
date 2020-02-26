"""Support for August doorbell camera."""

from august.activity import ActivityType
from august.util import update_doorbell_image_from_activity

from homeassistant.components.camera import Camera
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    AUGUST_DEVICE_UPDATE,
    DATA_AUGUST,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MIN_TIME_BETWEEN_DETAIL_UPDATES,
)

SCAN_INTERVAL = MIN_TIME_BETWEEN_DETAIL_UPDATES


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up August cameras."""
    data = hass.data[DOMAIN][config_entry.entry_id][DATA_AUGUST]
    devices = []

    for doorbell in data.doorbells:
        devices.append(AugustCamera(data, doorbell, DEFAULT_TIMEOUT))

    async_add_entities(devices, True)


class AugustCamera(Camera):
    """An implementation of a August security camera."""

    def __init__(self, data, doorbell, timeout):
        """Initialize a August security camera."""
        super().__init__()
        self._undo_dispatch_subscription = None
        self._data = data
        self._doorbell = doorbell
        self._doorbell_detail = None
        self._timeout = timeout
        self._image_url = None
        self._image_content = None
        self._firmware_version = None
        self._model = None

    @property
    def name(self):
        """Return the name of this device."""
        return self._doorbell.device_name

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._doorbell.has_subscription

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return True

    @property
    def brand(self):
        """Return the camera brand."""
        return DEFAULT_NAME

    @property
    def model(self):
        """Return the camera model."""
        return self._model

    async def async_camera_image(self):
        """Return bytes of camera image."""
        self._doorbell_detail = await self._data.async_get_doorbell_detail(
            self._doorbell.device_id
        )
        doorbell_activity = self._data.activity_stream.async_get_latest_device_activity(
            self._doorbell.device_id, [ActivityType.DOORBELL_MOTION]
        )

        if doorbell_activity is not None:
            update_doorbell_image_from_activity(
                self._doorbell_detail, doorbell_activity
            )

        if self._doorbell_detail is None:
            return None

        if self._image_url is not self._doorbell_detail.image_url:
            self._image_url = self._doorbell_detail.image_url
            self._image_content = await self.hass.async_add_executor_job(
                self._camera_image
            )
        return self._image_content

    async def async_update(self):
        """Update camera data."""
        self._doorbell_detail = await self._data.async_get_doorbell_detail(
            self._doorbell.device_id
        )

        if self._doorbell_detail is None:
            return None

        self._firmware_version = self._doorbell_detail.firmware_version
        self._model = self._doorbell_detail.model

    def _camera_image(self):
        """Return bytes of camera image."""
        return self._doorbell_detail.get_doorbell_image(timeout=self._timeout)

    @property
    def unique_id(self) -> str:
        """Get the unique id of the camera."""
        return f"{self._doorbell.device_id:s}_camera"

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._doorbell.device_id)},
            "name": self._doorbell.device_name + " Camera",
            "manufacturer": DEFAULT_NAME,
            "sw_version": self._firmware_version,
            "model": self._model,
        }

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._undo_dispatch_subscription = async_dispatcher_connect(
            self.hass, f"{AUGUST_DEVICE_UPDATE}-{self._doorbell.device_id}", update
        )

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        if self._undo_dispatch_subscription:
            self._undo_dispatch_subscription()

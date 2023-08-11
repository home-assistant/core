"""Support for Verisure cameras."""
from __future__ import annotations

import errno
import os

from verisure import Error as VerisureError

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GIID, DOMAIN, LOGGER, SERVICE_CAPTURE_SMARTCAM
from .coordinator import VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Verisure sensors based on a config entry."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CAPTURE_SMARTCAM,
        {},
        VerisureSmartcam.capture_smartcam.__name__,
    )

    assert hass.config.config_dir
    async_add_entities(
        VerisureSmartcam(coordinator, serial_number, hass.config.config_dir)
        for serial_number in coordinator.data["cameras"]
    )


class VerisureSmartcam(CoordinatorEntity[VerisureDataUpdateCoordinator], Camera):
    """Representation of a Verisure camera."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: VerisureDataUpdateCoordinator,
        serial_number: str,
        directory_path: str,
    ) -> None:
        """Initialize Verisure File Camera component."""
        super().__init__(coordinator)
        Camera.__init__(self)

        self._attr_unique_id = serial_number

        self.serial_number = serial_number
        self._directory_path = directory_path
        self._image: str | None = None
        self._image_id: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        area = self.coordinator.data["cameras"][self.serial_number]["device"]["area"]
        return DeviceInfo(
            name=area,
            suggested_area=area,
            manufacturer="Verisure",
            model="SmartCam",
            identifiers={(DOMAIN, self.serial_number)},
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_GIID]),
            configuration_url="https://mypages.verisure.com",
        )

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return image response."""
        self.check_imagelist()
        if not self._image:
            LOGGER.debug("No image to display")
            return None
        LOGGER.debug("Trying to open %s", self._image)
        with open(self._image, "rb") as file:
            return file.read()

    def check_imagelist(self) -> None:
        """Check the contents of the image list."""
        self.coordinator.update_smartcam_imageseries()

        new_image = None
        for image in self.coordinator.imageseries:
            if image["deviceLabel"] == self.serial_number:
                new_image = image
                break

        if not new_image:
            return

        new_image_id = new_image["mediaId"]
        if new_image_id in ("-1", self._image_id):
            LOGGER.debug("The image is the same, or loading image_id")
            return

        LOGGER.debug("Download new image %s", new_image_id)
        new_image_path = os.path.join(
            self._directory_path, "{}{}".format(new_image_id, ".jpg")
        )
        new_image_url = new_image["contentUrl"]
        self.coordinator.verisure.download_image(new_image_url, new_image_path)
        LOGGER.debug("Old image_id=%s", self._image_id)
        self.delete_image()

        self._image_id = new_image_id
        self._image = new_image_path

    def delete_image(self, _=None) -> None:
        """Delete an old image."""
        remove_image = os.path.join(
            self._directory_path, "{}{}".format(self._image_id, ".jpg")
        )
        try:
            os.remove(remove_image)
            LOGGER.debug("Deleting old image %s", remove_image)
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise

    def capture_smartcam(self) -> None:
        """Capture a new picture from a smartcam."""
        try:
            self.coordinator.smartcam_capture(self.serial_number)
            LOGGER.debug("Capturing new image from %s", self.serial_number)
        except VerisureError as ex:
            LOGGER.error("Could not capture image, %s", ex)

    async def async_added_to_hass(self) -> None:
        """Entity added to Home Assistant."""
        await super().async_added_to_hass()
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.delete_image)

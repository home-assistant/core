"""Support for Verisure cameras."""
from __future__ import annotations

import errno
import os
from typing import Any, Callable

from homeassistant.components.camera import Camera
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SMARTCAM, DOMAIN, LOGGER
from .coordinator import VerisureDataUpdateCoordinator


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[VerisureSmartcam]], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure Camera."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN]
    if not int(coordinator.config.get(CONF_SMARTCAM, 1)):
        return

    assert hass.config.config_dir
    add_entities(
        [
            VerisureSmartcam(hass, coordinator, serial_number, hass.config.config_dir)
            for serial_number in coordinator.data["cameras"]
        ]
    )


class VerisureSmartcam(CoordinatorEntity, Camera):
    """Representation of a Verisure camera."""

    coordinator = VerisureDataUpdateCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: VerisureDataUpdateCoordinator,
        serial_number: str,
        directory_path: str,
    ):
        """Initialize Verisure File Camera component."""
        super().__init__(coordinator)

        self.serial_number = serial_number
        self._directory_path = directory_path
        self._image = None
        self._image_id = None
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.delete_image)

    def camera_image(self) -> bytes | None:
        """Return image response."""
        self.check_imagelist()
        if not self._image:
            LOGGER.debug("No image to display")
            return
        LOGGER.debug("Trying to open %s", self._image)
        with open(self._image, "rb") as file:
            return file.read()

    def check_imagelist(self) -> None:
        """Check the contents of the image list."""
        self.coordinator.update_smartcam_imageseries()

        images = self.coordinator.imageseries.get("imageSeries", [])
        new_image_id = None
        for image in images:
            if image["deviceLabel"] == self.serial_number:
                new_image_id = image["image"][0]["imageId"]
                break

        if not new_image_id:
            return

        if new_image_id in ("-1", self._image_id):
            LOGGER.debug("The image is the same, or loading image_id")
            return

        LOGGER.debug("Download new image %s", new_image_id)
        new_image_path = os.path.join(
            self._directory_path, "{}{}".format(new_image_id, ".jpg")
        )
        self.coordinator.verisure.download_image(
            self.serial_number, new_image_id, new_image_path
        )
        LOGGER.debug("Old image_id=%s", self._image_id)
        self.delete_image()

        self._image_id = new_image_id
        self._image = new_image_path

    def delete_image(self) -> None:
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

    @property
    def name(self) -> str:
        """Return the name of this camera."""
        return self.coordinator.data["cameras"][self.serial_number]["area"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this camera."""
        return self.serial_number

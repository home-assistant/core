"""Platform for Miele image entity."""

import asyncio
import base64
import binascii
from dataclasses import dataclass
import logging
import time
from typing import Final, override

from aiohttp import ClientResponseError
from pymiele import MieleCamera as MieleCameraData

from homeassistant.components.image import (
    DEFAULT_CONTENT_TYPE,
    ImageEntity,
    ImageEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import MieleAppliance, StateStatus
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

PARALLEL_UPDATES = 1
_CACHE_TTL_SECONDS: Final = 60

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleImageDescription(ImageEntityDescription):
    """Class describing Miele image entities."""


@dataclass
class MieleImageDefinition:
    """Class for defining image entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleImageDescription


IMAGE_TYPES: Final[tuple[MieleImageDefinition, ...]] = (
    MieleImageDefinition(
        types=(MieleAppliance.OVEN,),
        description=MieleImageDescription(
            key="camera",
            translation_key="camera",
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the image platform."""
    coordinator = config_entry.runtime_data.coordinator
    added_devices: set[str] = set()

    def _async_add_new_devices() -> None:
        nonlocal added_devices
        new_devices_set, current_devices = coordinator.async_add_devices(added_devices)
        added_devices = current_devices

        async_add_entities(
            MieleImage(hass, coordinator, device_id, definition.description)
            for device_id, device in coordinator.data.devices.items()
            for definition in IMAGE_TYPES
            if device_id in new_devices_set and device.device_type in definition.types
        )

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
    _async_add_new_devices()


class MieleImage(MieleEntity, ImageEntity):
    """Representation of a Miele oven camera image."""

    entity_description: MieleImageDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: MieleImageDescription,
    ) -> None:
        """Initialize the image entity."""
        MieleEntity.__init__(self, coordinator, device_id, description)
        ImageEntity.__init__(self, hass)
        self._cached_image_bytes: bytes | None = None
        self._last_attempt_time: float | None = None
        self._fetch_lock = asyncio.Lock()

    @property
    @override
    def available(self) -> bool:
        """Return the availability of the entity."""
        return (
            super().available and self.device.state_status == StateStatus.in_use.value
        )

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return a link to the image as entity picture when available."""
        if not self.available:
            return None
        return super().entity_picture

    @override
    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if not self.available:
            return None

        async with self._fetch_lock:
            now = time.monotonic()
            if (
                self._last_attempt_time is not None
                and (now - self._last_attempt_time) < _CACHE_TTL_SECONDS
            ):
                return self._cached_image_bytes

            self._last_attempt_time = now
            try:
                camera_json = await self.api.get_camera(self._device_id)
            except ClientResponseError as err:
                _LOGGER.debug(
                    "Error fetching camera image for %s: Status: %s, Message: %s",
                    self.entity_id,
                    str(err.status),
                    err.message,
                )
                return None
            except TimeoutError:
                _LOGGER.debug("Timeout fetching camera image for %s", self.entity_id)
                return None

            image_data = MieleCameraData(camera_json).image()
            if not image_data:
                return None

            self._attr_content_type = DEFAULT_CONTENT_TYPE
            if image_data.startswith("data:") and "," in image_data:
                header, image_data = image_data.split(",", 1)
                if ";" in header:
                    self._attr_content_type = header[5:].split(";", 1)[0]

            try:
                decoded = base64.b64decode(image_data)
            except (binascii.Error, ValueError) as err:
                _LOGGER.debug(
                    "Error decoding camera image for %s: %s",
                    self.entity_id,
                    err,
                )
                return None

            image_changed = decoded != self._cached_image_bytes
            self._cached_image_bytes = decoded
            if image_changed:
                self._attr_image_last_updated = dt_util.utcnow()
                self.async_write_ha_state()
            return decoded

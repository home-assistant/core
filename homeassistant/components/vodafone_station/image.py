"""Vodafone Station image."""

from __future__ import annotations

from io import BytesIO
from typing import Final, cast

from aiovodafone.const import WIFI_DATA

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import _LOGGER
from .coordinator import VodafoneConfigEntry, VodafoneStationRouter

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


IMAGE_TYPES: Final = (
    ImageEntityDescription(
        key="guest",
        translation_key="guest",
    ),
    ImageEntityDescription(
        key="guest_5g",
        translation_key="guest_5g",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VodafoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Guest WiFi QR code for device."""
    _LOGGER.debug("Setting up Vodafone Station images")

    coordinator = entry.runtime_data

    wifi = coordinator.data.wifi

    async_add_entities(
        VodafoneGuestWifiQRImage(hass, coordinator, image_desc)
        for image_desc in IMAGE_TYPES
        if image_desc.key in wifi[WIFI_DATA]
        and "qr_code" in wifi[WIFI_DATA][image_desc.key]
    )


class VodafoneGuestWifiQRImage(
    CoordinatorEntity[VodafoneStationRouter],
    ImageEntity,
):
    """Implementation of the Guest wifi QR code image entity."""

    _attr_content_type = "image/png"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: VodafoneStationRouter,
        description: ImageEntityDescription,
    ) -> None:
        """Initialize QR code image entity."""
        super().__init__(coordinator)
        ImageEntity.__init__(self, hass)

        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}-qr-code"
        self._cached_qr_code: bytes | None = None

    @property
    def _qr_code(self) -> bytes:
        """Return QR code bytes."""
        qr_code = cast(
            BytesIO,
            self.coordinator.data.wifi[WIFI_DATA][self.entity_description.key][
                "qr_code"
            ],
        )
        return qr_code.getvalue()

    async def async_added_to_hass(self) -> None:
        """Set the update time."""
        self._attr_image_last_updated = dt_util.utcnow()
        await super().async_added_to_hass()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        If the coordinator has updated the QR code, we can update the image.
        """
        qr_code = self._qr_code
        if self._cached_qr_code != qr_code:
            self._cached_qr_code = qr_code
            self._attr_image_last_updated = dt_util.utcnow()

        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return QR code image."""
        return self._qr_code

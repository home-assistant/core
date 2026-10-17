"""Image platform for Threema Gateway integration."""

import io
from typing import override

import segno

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ThreemaConfigEntry
from .client import derive_public_key
from .const import DOMAIN

PARALLEL_UPDATES = 0


def _generate_qr_code(gateway_id: str, public_key: str) -> bytes:
    """Return the Threema ID QR code of the gateway as SVG."""
    buffer = io.BytesIO()
    qr_code = segno.make(f"3mid:{gateway_id},{public_key}", micro=False)
    qr_code.save(buffer, kind="svg", scale=5, light="#fff")
    return buffer.getvalue()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThreemaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the gateway QR code for end-to-end encrypted gateways."""
    client = entry.runtime_data
    if client.private_key is None:
        return

    qr_code = await hass.async_add_executor_job(
        _generate_qr_code,
        client.gateway_id,
        derive_public_key(client.private_key),
    )
    async_add_entities([ThreemaQRCodeImage(hass, entry, qr_code)])


class ThreemaQRCodeImage(ImageEntity):
    """QR code to verify the gateway's public key in the Threema app."""

    _attr_has_entity_name = True
    _attr_translation_key = "gateway_qr_code"
    _attr_content_type = "image/svg+xml"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, hass: HomeAssistant, entry: ThreemaConfigEntry, qr_code: bytes
    ) -> None:
        """Initialize the QR code image entity."""
        super().__init__(hass)
        gateway_id = entry.runtime_data.gateway_id
        self._qr_code = qr_code

        self._attr_unique_id = f"{gateway_id}_qr_code"
        self._attr_image_last_updated = dt_util.utcnow()
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Threema",
            model="Gateway",
            identifiers={(DOMAIN, gateway_id)},
            name=entry.title,
        )

    @override
    async def async_image(self) -> bytes | None:
        """Return the QR code."""
        return self._qr_code

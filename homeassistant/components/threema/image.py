"""Image platform for Threema Gateway integration."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import qrcode

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThreemaConfigEntry
from .const import CONF_GATEWAY_ID, CONF_PUBLIC_KEY, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThreemaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Threema image entities from a config entry."""
    if entry.data.get(CONF_PUBLIC_KEY):
        async_add_entities([ThreemaQRCodeImage(hass, entry)])


class ThreemaQRCodeImage(ImageEntity):
    """Image entity that displays the gateway's public key as a QR code."""

    _attr_has_entity_name = True
    _attr_translation_key = "gateway_qr_code"
    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, entry: ThreemaConfigEntry) -> None:
        """Initialize the QR code image entity."""
        super().__init__(hass)
        self._entry = entry
        self._qr_image_bytes: bytes | None = None

        gateway_id = entry.data[CONF_GATEWAY_ID]
        self._attr_unique_id = f"{gateway_id}_qr_code"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, gateway_id)},
            name=f"Threema {gateway_id}",
            manufacturer="Threema",
            model="Gateway",
            configuration_url="https://gateway.threema.ch",
        )

    async def async_added_to_hass(self) -> None:
        """Generate QR code when entity is added to hass."""
        await super().async_added_to_hass()
        await self.hass.async_add_executor_job(self._generate_qr_code)
        if self._qr_image_bytes is not None:
            self._attr_image_last_updated = datetime.now(UTC)

    def _generate_qr_code(self) -> None:
        """Generate QR code from the public key."""
        public_key = self._entry.data.get(CONF_PUBLIC_KEY)
        if not public_key:
            return

        gateway_id = self._entry.data[CONF_GATEWAY_ID]
        public_key_hex = public_key.replace("public:", "").strip().lower()
        qr_data = f"3mid:{gateway_id},{public_key_hex}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        self._qr_image_bytes = buffer.getvalue()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._qr_image_bytes is not None

    async def async_image(self) -> bytes | None:
        """Return the image bytes."""
        return self._qr_image_bytes

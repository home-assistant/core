"""FRITZ image integration."""

from __future__ import annotations

from io import BytesIO
import logging

from requests.exceptions import RequestException

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from .coordinator import AvmWrapper, FritzConfigEntry
from .entity import FritzBoxBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up guest WiFi QR code for device."""
    avm_wrapper = entry.runtime_data

    guest_wifi_info = await hass.async_add_executor_job(
        avm_wrapper.fritz_guest_wifi.get_info
    )

    async_add_entities(
        [
            FritzGuestWifiQRImage(
                hass, avm_wrapper, entry.title, guest_wifi_info["NewSSID"]
            )
        ]
    )


class FritzGuestWifiQRImage(FritzBoxBaseEntity, ImageEntity):
    """Implementation of the FritzBox guest wifi QR code image entity."""

    _attr_content_type = "image/png"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        ssid: str,
    ) -> None:
        """Initialize the image entity."""
        self._attr_name = ssid
        self._attr_unique_id = slugify(f"{avm_wrapper.unique_id}-{ssid}-qr-code")
        self._current_qr_bytes: bytes | None = None
        super().__init__(avm_wrapper, device_friendly_name)
        ImageEntity.__init__(self, hass)

    async def _fetch_image(self) -> bytes:
        """Fetch the QR code from the Fritz!Box."""
        qr_stream: BytesIO = await self.hass.async_add_executor_job(
            self._avm_wrapper.fritz_guest_wifi.get_wifi_qr_code, "png"
        )
        qr_bytes = qr_stream.getvalue()
        _LOGGER.debug("fetched %s bytes", len(qr_bytes))

        return qr_bytes

    async def async_added_to_hass(self) -> None:
        """Fetch and set initial data and state."""
        self._current_qr_bytes = await self._fetch_image()
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_update(self) -> None:
        """Update the image entity data."""
        try:
            qr_bytes = await self._fetch_image()
        except RequestException:
            self._current_qr_bytes = None
            self._attr_image_last_updated = None
            self.async_write_ha_state()
            return

        if self._current_qr_bytes != qr_bytes:
            dt_now = dt_util.utcnow()
            _LOGGER.debug("qr code has changed, reset image last updated property")
            self._attr_image_last_updated = dt_now
            self._current_qr_bytes = qr_bytes
            self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._current_qr_bytes

"""FRITZ image integration."""

from __future__ import annotations

from io import BytesIO
import logging

from requests.exceptions import RequestException

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN, Platform
from .coordinator import AvmWrapper, FritzConfigEntry
from .entity import FritzBoxBaseEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def _migrate_to_new_unique_id(
    hass: HomeAssistant, avm_wrapper: AvmWrapper, ssid: str
) -> None:
    """Migrate old unique id to new unique id."""

    old_unique_id = slugify(f"{avm_wrapper.unique_id}-{ssid}-qr-code")
    new_unique_id = f"{avm_wrapper.unique_id}-guest_wifi_qr_code"

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        Platform.IMAGE,
        DOMAIN,
        old_unique_id,
    )

    if entity_id is None:
        return

    entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)
    _LOGGER.debug(
        "Migrating guest Wi-Fi image unique_id from [%s] to [%s]",
        old_unique_id,
        new_unique_id,
    )


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

    await _migrate_to_new_unique_id(hass, avm_wrapper, guest_wifi_info["NewSSID"])

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
        self._attr_unique_id = f"{avm_wrapper.unique_id}-guest_wifi_qr_code"
        self._current_qr_bytes: bytes | None = None
        super().__init__(avm_wrapper, device_friendly_name)
        ImageEntity.__init__(self, hass)

    def _fetch_image(self) -> bytes:
        """Fetch the QR code from the Fritz!Box."""
        qr_stream: BytesIO = self._avm_wrapper.fritz_guest_wifi.get_wifi_qr_code(
            "png", border=2
        )
        qr_bytes = qr_stream.getvalue()
        _LOGGER.debug("fetched %s bytes", len(qr_bytes))

        return qr_bytes

    async def async_added_to_hass(self) -> None:
        """Fetch and set initial data and state."""
        self._current_qr_bytes = await self.hass.async_add_executor_job(
            self._fetch_image
        )
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_update(self) -> None:
        """Update the image entity data."""
        try:
            qr_bytes = await self.hass.async_add_executor_job(self._fetch_image)
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

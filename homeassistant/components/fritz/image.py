"""FRITZ image integration."""

from io import BytesIO
from typing import override

from requests.exceptions import RequestException

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN, LOGGER
from .coordinator import AvmWrapper, FritzConfigEntry

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
    LOGGER.debug(
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
        [FritzGuestWifiQRImage(hass, avm_wrapper, guest_wifi_info["NewSSID"])]
    )


class FritzGuestWifiQRImage(CoordinatorEntity[AvmWrapper], ImageEntity):
    """Implementation of the FritzBox guest wifi QR code image entity."""

    _attr_content_type = "image/png"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        avm_wrapper: AvmWrapper,
        ssid: str,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(avm_wrapper)
        ImageEntity.__init__(self, hass)
        self._attr_name = ssid
        self._attr_unique_id = f"{avm_wrapper.unique_id}-guest_wifi_qr_code"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, avm_wrapper.mac)},
            identifiers={(DOMAIN, avm_wrapper.unique_id)},
        )
        self._current_qr_bytes: bytes | None = None
        self._guest_wifi_fingerprint: int | None = None

    def _fetch_image(self) -> bytes:
        """Fetch the QR code from the Fritz!Box."""
        qr_stream: BytesIO = self.coordinator.fritz_guest_wifi.get_wifi_qr_code(
            "png", border=2
        )
        qr_bytes = qr_stream.getvalue()
        LOGGER.debug("fetched %s bytes", len(qr_bytes))

        return qr_bytes

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(await self.coordinator.async_register_guest_wifi())
        self._async_update_guest_wifi()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_guest_wifi()
        super()._handle_coordinator_update()

    @callback
    def _async_update_guest_wifi(self) -> None:
        """Drop the cached QR code when the guest Wi-Fi changed."""
        fingerprint = self.coordinator.data["guest_wifi"]
        if fingerprint == self._guest_wifi_fingerprint:
            return
        LOGGER.debug("qr code has changed, reset image last updated property")
        self._guest_wifi_fingerprint = fingerprint
        self._current_qr_bytes = None
        self._attr_image_last_updated = dt_util.utcnow()

    @override
    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if self._current_qr_bytes is None:
            try:
                self._current_qr_bytes = await self.hass.async_add_executor_job(
                    self._fetch_image
                )
            except RequestException:
                return None
        return self._current_qr_bytes

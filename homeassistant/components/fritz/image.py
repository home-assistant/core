"""FRITZ image integration."""

from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN, Platform
from .coordinator import AvmWrapper, FritzConfigEntry

_LOGGER = logging.getLogger(__name__)

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


class FritzGuestWifiQRImage(CoordinatorEntity[AvmWrapper], ImageEntity):
    """Implementation of the FritzBox guest wifi QR code image entity."""

    _attr_content_type = "image/png"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = False

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
        self._device_name = device_friendly_name
        self._current_qr_bytes: bytes | None = None
        CoordinatorEntity.__init__(self, avm_wrapper)
        ImageEntity.__init__(self, hass)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.coordinator.mac)},
            identifiers={(DOMAIN, self.coordinator.unique_id)},
        )

    async def async_added_to_hass(self) -> None:
        """Set initial data and register coordinator update listener."""
        await super().async_added_to_hass()
        qr_bytes = self.coordinator.data.get("guest_wifi_qr_bytes")
        if qr_bytes is not None:
            self._current_qr_bytes = qr_bytes
            self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.last_update_success:
            self._current_qr_bytes = None
            self._attr_image_last_updated = None
            self.async_write_ha_state()
            return

        qr_bytes = self.coordinator.data.get("guest_wifi_qr_bytes")

        if qr_bytes is None:
            self._current_qr_bytes = None
            self._attr_image_last_updated = None
            self.async_write_ha_state()
            return

        if self._current_qr_bytes != qr_bytes:
            _LOGGER.debug("qr code has changed, reset image last updated property")
            self._attr_image_last_updated = dt_util.utcnow()
            self._current_qr_bytes = qr_bytes
            self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._current_qr_bytes

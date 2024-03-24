"""Image platform for UniFi Network integration.

Support for QR code for guest WLANs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.wlans import Wlans
from aiounifi.models.api import ApiItemT
from aiounifi.models.wlan import Wlan

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .entity import (
    HandlerT,
    UnifiEntity,
    UnifiEntityDescription,
    async_wlan_available_fn,
    async_wlan_device_info_fn,
)
from .hub import UnifiHub


@callback
def async_wlan_qr_code_image_fn(hub: UnifiHub, wlan: Wlan) -> bytes:
    """Calculate receiving data transfer value."""
    return hub.api.wlans.generate_wlan_qr_code(wlan)


@dataclass(frozen=True, kw_only=True)
class UnifiImageEntityDescription(
    ImageEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi image entity."""

    image_fn: Callable[[UnifiHub, ApiItemT], bytes]
    value_fn: Callable[[ApiItemT], str | None]


ENTITY_DESCRIPTIONS: tuple[UnifiImageEntityDescription, ...] = (
    UnifiImageEntityDescription[Wlans, Wlan](
        key="WLAN QR Code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.wlans,
        available_fn=async_wlan_available_fn,
        device_info_fn=async_wlan_device_info_fn,
        name_fn=lambda wlan: "QR Code",
        object_fn=lambda api, obj_id: api.wlans[obj_id],
        unique_id_fn=lambda hub, obj_id: f"qr_code-{obj_id}",
        image_fn=async_wlan_qr_code_image_fn,
        value_fn=lambda obj: obj.x_passphrase,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up image platform for UniFi Network integration."""
    UnifiHub.get_hub(hass, config_entry).entity_loader.register_platform(
        async_add_entities,
        UnifiImageEntity,
        ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiImageEntity(UnifiEntity[HandlerT, ApiItemT], ImageEntity):
    """Base representation of a UniFi image."""

    entity_description: UnifiImageEntityDescription[HandlerT, ApiItemT]
    _attr_content_type = "image/png"

    current_image: bytes | None = None
    previous_value: str | None = None

    def __init__(
        self,
        obj_id: str,
        hub: UnifiHub,
        description: UnifiEntityDescription[HandlerT, ApiItemT],
    ) -> None:
        """Initiatlize UniFi Image entity."""
        super().__init__(obj_id, hub, description)
        ImageEntity.__init__(self, hub.hass)

    def image(self) -> bytes | None:
        """Return bytes of image."""
        if self.current_image is None:
            description = self.entity_description
            obj = description.object_fn(self.hub.api, self._obj_id)
            self.current_image = description.image_fn(self.hub, obj)
        return self.current_image

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state."""
        description = self.entity_description
        obj = description.object_fn(self.hub.api, self._obj_id)
        if (value := description.value_fn(obj)) != self.previous_value:
            self.previous_value = value
            self.current_image = None
            self._attr_image_last_updated = dt_util.utcnow()

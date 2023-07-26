"""Image platform for UniFi Network integration.

Support for QR code for guest WLANs.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

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

from .const import DOMAIN as UNIFI_DOMAIN
from .controller import UniFiController
from .entity import (
    HandlerT,
    UnifiEntity,
    UnifiEntityDescription,
    async_wlan_device_info_fn,
)


@callback
def async_wlan_qr_code_image_fn(controller: UniFiController, wlan: Wlan) -> bytes:
    """Calculate receiving data transfer value."""
    return controller.api.wlans.generate_wlan_qr_code(wlan)


@dataclass
class UnifiImageEntityDescriptionMixin(Generic[HandlerT, ApiItemT]):
    """Validate and load entities from different UniFi handlers."""

    image_fn: Callable[[UniFiController, ApiItemT], bytes]
    value_fn: Callable[[ApiItemT], str]


@dataclass
class UnifiImageEntityDescription(
    ImageEntityDescription,
    UnifiEntityDescription[HandlerT, ApiItemT],
    UnifiImageEntityDescriptionMixin[HandlerT, ApiItemT],
):
    """Class describing UniFi image entity."""


ENTITY_DESCRIPTIONS: tuple[UnifiImageEntityDescription, ...] = (
    UnifiImageEntityDescription[Wlans, Wlan](
        key="WLAN QR Code",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
        entity_registry_enabled_default=False,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.wlans,
        available_fn=lambda controller, _: controller.available,
        device_info_fn=async_wlan_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda _: "QR Code",
        object_fn=lambda api, obj_id: api.wlans[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"qr_code-{obj_id}",
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
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.register_platform_add_entities(
        UnifiImageEntity, ENTITY_DESCRIPTIONS, async_add_entities
    )


class UnifiImageEntity(UnifiEntity[HandlerT, ApiItemT], ImageEntity):
    """Base representation of a UniFi image."""

    entity_description: UnifiImageEntityDescription[HandlerT, ApiItemT]
    _attr_content_type = "image/png"

    current_image: bytes | None = None
    previous_value = ""

    def __init__(
        self,
        obj_id: str,
        controller: UniFiController,
        description: UnifiEntityDescription[HandlerT, ApiItemT],
    ) -> None:
        """Initiatlize UniFi Image entity."""
        super().__init__(obj_id, controller, description)
        ImageEntity.__init__(self, controller.hass)

    def image(self) -> bytes | None:
        """Return bytes of image."""
        if self.current_image is None:
            description = self.entity_description
            obj = description.object_fn(self.controller.api, self._obj_id)
            self.current_image = description.image_fn(self.controller, obj)
        return self.current_image

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state."""
        description = self.entity_description
        obj = description.object_fn(self.controller.api, self._obj_id)
        if (value := description.value_fn(obj)) != self.previous_value:
            self.previous_value = value
            self.current_image = None
            self._attr_image_last_updated = dt_util.utcnow()

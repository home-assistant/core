"""Text entities for UniFi Protect."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyunifiprotect.data import (
    Camera,
    DoorbellMessageType,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
)

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPATCH_ADOPT, DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity, async_all_device_entities
from .models import PermRequired, ProtectSetableKeysMixin, T
from .utils import async_dispatch_id as _ufpd


@dataclass(frozen=True, kw_only=True)
class ProtectTextEntityDescription(ProtectSetableKeysMixin[T], TextEntityDescription):
    """Describes UniFi Protect Text entity."""


def _get_doorbell_current(obj: Camera) -> str | None:
    if obj.lcd_message is None:
        return obj.api.bootstrap.nvr.doorbell_settings.default_message_text
    return obj.lcd_message.text


async def _set_doorbell_message(obj: Camera, message: str) -> None:
    await obj.set_lcd_text(DoorbellMessageType.CUSTOM_MESSAGE, text=message)


CAMERA: tuple[ProtectTextEntityDescription, ...] = (
    ProtectTextEntityDescription(
        key="doorbell",
        name="Doorbell",
        entity_category=EntityCategory.CONFIG,
        ufp_value_fn=_get_doorbell_current,
        ufp_set_method_fn=_set_doorbell_message,
        ufp_required_field="feature_flags.has_lcd_screen",
        ufp_perm=PermRequired.WRITE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities = async_all_device_entities(
            data,
            ProtectDeviceText,
            camera_descs=CAMERA,
            ufp_device=device,
        )
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_ADOPT), _add_new_device)
    )

    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectDeviceText,
        camera_descs=CAMERA,
    )

    async_add_entities(entities)


class ProtectDeviceText(ProtectDeviceEntity, TextEntity):
    """A Ubiquiti UniFi Protect Sensor."""

    entity_description: ProtectTextEntityDescription

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel,
        description: ProtectTextEntityDescription,
    ) -> None:
        """Initialize an UniFi Protect sensor."""
        super().__init__(data, device, description)

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_ufp_value(self.device)

    @callback
    def _async_get_state_attrs(self) -> tuple[Any, ...]:
        """Retrieve data that goes into the current state of the entity.

        Called before and after updating entity and state is only written if there
        is a change.
        """

        return (self._attr_available, self._attr_native_value)

    async def async_set_value(self, value: str) -> None:
        """Change the value."""

        await self.entity_description.ufp_set(self.device, value)

"""Text entities for UniFi Protect."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from uiprotect.data import (
    Camera,
    DoorbellMessageType,
    ModelType,
    ProtectAdoptableDeviceModel,
)

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity, async_all_device_entities
from .models import PermRequired, ProtectEntityDescription, ProtectSetableKeysMixin, T


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

_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: CAMERA,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        async_add_entities(
            async_all_device_entities(
                data,
                ProtectDeviceText,
                model_descriptions=_MODEL_DESCRIPTIONS,
                ufp_device=device,
            )
        )

    data.async_subscribe_adopt(_add_new_device)
    async_add_entities(
        async_all_device_entities(
            data, ProtectDeviceText, model_descriptions=_MODEL_DESCRIPTIONS
        )
    )


class ProtectDeviceText(ProtectDeviceEntity, TextEntity):
    """A Ubiquiti UniFi Protect Sensor."""

    entity_description: ProtectTextEntityDescription
    _state_attrs = ("_attr_available", "_attr_native_value")

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_ufp_value(self.device)

    async def async_set_value(self, value: str) -> None:
        """Change the value."""
        await self.entity_description.ufp_set(self.device, value)

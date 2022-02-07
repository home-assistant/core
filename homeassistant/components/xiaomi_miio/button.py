"""Support for Xiaomi buttons."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import suppress
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass, 
    ButtonEntity, 
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_MODEL,
    DOMAIN,
    FEATURE_FLAGS_AIRFRESH_A1,
    FEATURE_FLAGS_AIRFRESH_T2017,
    FEATURE_RESET_DUST_FILTER,
    FEATURE_RESET_UPPER_FILTER,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_A1,
    MODEL_AIRFRESH_T2017,
)

from .device import XiaomiCoordinatedMiioEntity

DATA_KEY = "button.xiaomi_miio"

ATTR_RESET_DUST_FILTER = "reset_dust_filter"
ATTR_RESET_UPPER_FILTER = "reset_upper_filter"

MODEL_TO_FEATURES_MAP = {
    MODEL_AIRFRESH_A1: FEATURE_FLAGS_AIRFRESH_A1,
    MODEL_AIRFRESH_T2017: FEATURE_FLAGS_AIRFRESH_T2017,
}

@dataclass
class XiaomiMiioButtonDescription(ButtonEntityDescription):
    """A class that describes button entities."""

    feature: int | None = None
    method_press: str | None = None
    available_with_device_off: bool = True


BUTTON_TYPES = (
    XiaomiMiioButtonDescription(
        key=ATTR_RESET_DUST_FILTER,
        feature=FEATURE_RESET_DUST_FILTER,
        name="Reset dust filter",
        icon="mdi:air-filter",
        method_press="async_reset_dust_filter",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    XiaomiMiioButtonDescription(
        key=ATTR_RESET_UPPER_FILTER,
        feature=FEATURE_RESET_UPPER_FILTER,
        name="Reset upper filter",
        icon="mdi:air-filter",
        method_press="async_reset_upper_filter",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities = []
    model = config_entry.data[CONF_MODEL]
    unique_id = config_entry.unique_id
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    device_features = 0

    if model in MODEL_TO_FEATURES_MAP:
        device_features = MODEL_TO_FEATURES_MAP[model]

    for description in BUTTON_TYPES:
        if description.feature & device_features:
            entities.append(
                XiaomiGenericCoordinatedButton(
                    f"{config_entry.title} {description.name}",
                    device,
                    config_entry,
                    f"{description.key}_{unique_id}",
                    coordinator,
                    description,
                )
            )

    async_add_entities(entities)


class XiaomiGenericCoordinatedButton(XiaomiCoordinatedMiioEntity, ButtonEntity):
    """A button implementation for Xiaomi."""

    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, name, device, entry, unique_id, coordinator, description):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id, coordinator)
        self.entity_description = description

    @property
    def available(self):
        """Return true when state is known."""
        if (
            super().available
            and not self.coordinator.data.is_on
            and not self.entity_description.available_with_device_off
        ):
            return False
        return super().available

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        method = getattr(self, self.entity_description.method_press)
        await method()

    async def async_reset_dust_filter(self) -> None:
        """Reset the dust filter lifetime and usage."""
        await self._try_command(
            "Resetting the dust filter lifetime of the miio device failed.",
            self._device.reset_dust_filter,
        )

    async def async_reset_upper_filter(self) -> None:
        """Reset the upper filter lifetime and usage."""
        await self._try_command(
            "Resetting the upper filter lifetime of the miio device failed.",
            self._device.reset_upper_filter,
        )

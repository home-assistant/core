"""Support for Tuya siren."""

from __future__ import annotations

from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity

SIRENS: dict[DeviceCategory, tuple[SirenEntityDescription, ...]] = {
    DeviceCategory.CO2BJ: (
        SirenEntityDescription(
            key=DPCode.ALARM_SWITCH,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.DGNBJ: (
        SirenEntityDescription(
            key=DPCode.ALARM_SWITCH,
        ),
    ),
    DeviceCategory.SGBJ: (
        SirenEntityDescription(
            key=DPCode.ALARM_SWITCH,
        ),
    ),
    DeviceCategory.SP: (
        SirenEntityDescription(
            key=DPCode.SIREN_SWITCH,
        ),
    ),
}

# Smart Camera - Low power consumption camera (duplicate of `sp`)
SIRENS[DeviceCategory.DGHSXJ] = SIRENS[DeviceCategory.SP]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya siren dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya siren."""
        entities: list[TuyaSirenEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := SIRENS.get(device.category):
                entities.extend(
                    TuyaSirenEntity(device, manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSirenEntity(TuyaEntity, SirenEntity):
    """Tuya Siren Entity."""

    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
    _attr_name = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: SirenEntityDescription,
    ) -> None:
        """Init Tuya Siren."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return self.device.status.get(self.entity_description.key, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        self._send_command([{"code": self.entity_description.key, "value": True}])

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        self._send_command([{"code": self.entity_description.key, "value": False}])

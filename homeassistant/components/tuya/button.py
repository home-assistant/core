"""Support for Tuya buttons."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import DPCodeBooleanWrapper

BUTTONS: dict[DeviceCategory, tuple[ButtonEntityDescription, ...]] = {
    DeviceCategory.HXD: (
        ButtonEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="snooze",
        ),
    ),
    DeviceCategory.MSP: (
        ButtonEntityDescription(
            key=DPCode.FACTORY_RESET,
            translation_key="factory_reset",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        ButtonEntityDescription(
            key=DPCode.MANUAL_CLEAN,
            translation_key="manual_clean",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SD: (
        ButtonEntityDescription(
            key=DPCode.RESET_DUSTER_CLOTH,
            translation_key="reset_duster_cloth",
            entity_category=EntityCategory.CONFIG,
        ),
        ButtonEntityDescription(
            key=DPCode.RESET_EDGE_BRUSH,
            translation_key="reset_edge_brush",
            entity_category=EntityCategory.CONFIG,
        ),
        ButtonEntityDescription(
            key=DPCode.RESET_FILTER,
            translation_key="reset_filter",
            entity_category=EntityCategory.CONFIG,
        ),
        ButtonEntityDescription(
            key=DPCode.RESET_MAP,
            translation_key="reset_map",
            entity_category=EntityCategory.CONFIG,
        ),
        ButtonEntityDescription(
            key=DPCode.RESET_ROLL_BRUSH,
            translation_key="reset_roll_brush",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya buttons dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya buttons."""
        entities: list[TuyaButtonEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := BUTTONS.get(device.category):
                entities.extend(
                    TuyaButtonEntity(device, manager, description, dpcode_wrapper)
                    for description in descriptions
                    if (
                        dpcode_wrapper := DPCodeBooleanWrapper.find_dpcode(
                            device, description.key, prefer_function=True
                        )
                    )
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaButtonEntity(TuyaEntity, ButtonEntity):
    """Tuya Button Device."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: ButtonEntityDescription,
        dpcode_wrapper: DPCodeBooleanWrapper,
    ) -> None:
        """Init Tuya button."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._dpcode_wrapper = dpcode_wrapper

    async def async_press(self) -> None:
        """Press the button."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, True)

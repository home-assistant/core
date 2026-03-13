"""Support for Tuya text."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import DeviceWrapper, DPCodeRawWrapper


class _Base64StringWrapper(DPCodeRawWrapper):
    """Wrapper for Raw type that keeps base64 strings without decoding."""

    def read_device_status(self, device: CustomerDevice) -> str | None:
        """Read device status and return base64 string without decoding."""
        if (value := device.status.get(self.dpcode)) is None:
            return None
        return str(value)

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: str) -> str:
        """Convert string value directly (already in base64 format)."""
        return value


TEXTS: dict[DeviceCategory, tuple[TextEntityDescription, ...]] = {
    DeviceCategory.CWWSQ: (
        TextEntityDescription(
            key=DPCode.MEAL_PLAN,
            translation_key="meal_plan",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya text dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya text."""
        entities: list[TuyaTextEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := TEXTS.get(device.category):
                entities.extend(
                    TuyaTextEntity(device, manager, description, dpcode_wrapper)
                    for description in descriptions
                    if (
                        dpcode_wrapper := _Base64StringWrapper.find_dpcode(
                            device, description.key, prefer_function=True
                        )
                    )
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaTextEntity(TuyaEntity, TextEntity):
    """Tuya Text Entity."""

    _attr_native_max = 255

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TextEntityDescription,
        dpcode_wrapper: DeviceWrapper[str],
    ) -> None:
        """Init Tuya text."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._dpcode_wrapper = dpcode_wrapper

    @property
    def native_value(self) -> str | None:
        """Return the current text value."""
        return self._read_wrapper(self._dpcode_wrapper)

    async def async_set_value(self, value: str) -> None:
        """Update the text value."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, value)

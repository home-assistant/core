"""Support for Tuya valves."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import DPCodeBooleanWrapper

VALVES: dict[DeviceCategory, tuple[ValveEntityDescription, ...]] = {
    DeviceCategory.SFKZQ: (
        ValveEntityDescription(
            key=DPCode.SWITCH,
            translation_key="valve",
            device_class=ValveDeviceClass.WATER,
        ),
        ValveEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_valve",
            translation_placeholders={"index": "1"},
            device_class=ValveDeviceClass.WATER,
        ),
        ValveEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="indexed_valve",
            translation_placeholders={"index": "2"},
            device_class=ValveDeviceClass.WATER,
        ),
        ValveEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="indexed_valve",
            translation_placeholders={"index": "3"},
            device_class=ValveDeviceClass.WATER,
        ),
        ValveEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="indexed_valve",
            translation_placeholders={"index": "4"},
            device_class=ValveDeviceClass.WATER,
        ),
        ValveEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="indexed_valve",
            translation_placeholders={"index": "5"},
            device_class=ValveDeviceClass.WATER,
        ),
        ValveEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="indexed_valve",
            translation_placeholders={"index": "6"},
            device_class=ValveDeviceClass.WATER,
        ),
        ValveEntityDescription(
            key=DPCode.SWITCH_7,
            translation_key="indexed_valve",
            translation_placeholders={"index": "7"},
            device_class=ValveDeviceClass.WATER,
        ),
        ValveEntityDescription(
            key=DPCode.SWITCH_8,
            translation_key="indexed_valve",
            translation_placeholders={"index": "8"},
            device_class=ValveDeviceClass.WATER,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tuya valves dynamically through tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya valve."""
        entities: list[TuyaValveEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := VALVES.get(device.category):
                entities.extend(
                    TuyaValveEntity(device, manager, description, dpcode_wrapper)
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


class TuyaValveEntity(TuyaEntity, ValveEntity):
    """Tuya Valve Device."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: ValveEntityDescription,
        dpcode_wrapper: DPCodeBooleanWrapper,
    ) -> None:
        """Init TuyaValveEntity."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._dpcode_wrapper = dpcode_wrapper

    @property
    def is_closed(self) -> bool | None:
        """Return if the valve is closed."""
        if (is_open := self._read_wrapper(self._dpcode_wrapper)) is None:
            return None
        return not is_open

    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, True)

    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, False)

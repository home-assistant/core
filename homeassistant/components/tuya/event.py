"""Support for Tuya event entities."""

from __future__ import annotations

from base64 import b64decode
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode, DPType
from .entity import TuyaEntity
from .models import find_dpcode
from .util import get_dpcode


@dataclass(frozen=True)
class TuyaEventEntityDescription(EventEntityDescription):
    """Describes Tuya event entity."""

    event_type_conversion: Callable[[Any], str] | None = None
    event_attributes_conversion: Callable[[Any], dict[str, Any]] | None = None


# All descriptions can be found here. Mostly the Enum data types in the
# default status set of each category (that don't have a set instruction)
# end up being events.
EVENTS: dict[DeviceCategory, tuple[TuyaEventEntityDescription, ...]] = {
    DeviceCategory.SP: (
        TuyaEventEntityDescription(
            key=DPCode.ALARM_MESSAGE,
            device_class=EventDeviceClass.DOORBELL,
            translation_key="alarm_message",
            event_type_conversion=lambda value: DPCode.ALARM_MESSAGE,
            event_attributes_conversion=lambda value: {
                "message": b64decode(value).decode("utf-8")
            },
        ),
        TuyaEventEntityDescription(
            key=DPCode.DOORBELL_PIC,
            device_class=EventDeviceClass.DOORBELL,
            translation_key="doorbell_picture",
            event_type_conversion=lambda value: DPCode.DOORBELL_PIC,
            event_attributes_conversion=lambda value: {
                "picture": b64decode(value).decode("utf-8")
            },
        ),
    ),
    DeviceCategory.WXKG: (
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE1,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "1"},
        ),
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE2,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "2"},
        ),
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE3,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "3"},
        ),
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE4,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "4"},
        ),
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE5,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "5"},
        ),
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE6,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "6"},
        ),
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE7,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "7"},
        ),
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE8,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "8"},
        ),
        TuyaEventEntityDescription(
            key=DPCode.SWITCH_MODE9,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "9"},
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya events dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[TuyaEventEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := EVENTS.get(device.category):
                for description in descriptions:
                    dpcode = description.key
                    if dpcode in device.status:
                        entities.append(TuyaEventEntity(device, manager, description))

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaEventEntity(TuyaEntity, EventEntity):
    """Tuya Event Entity."""

    entity_description: TuyaEventEntityDescription

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaEventEntityDescription,
    ) -> None:
        """Init Tuya event entity."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        if dpcode := find_dpcode(self.device, description.key, dptype=DPType.ENUM):
            self._attr_event_types: list[str] = dpcode.range
        elif dpcode := get_dpcode(device, description.key):
            self._attr_event_types: list[str] = [dpcode]

    async def _handle_state_update(
        self,
        updated_status_properties: list[str] | None,
        dp_timestamps: dict | None = None,
    ) -> None:
        if (
            updated_status_properties is None
            or self.entity_description.key not in updated_status_properties
        ):
            return

        value = self.device.status.get(self.entity_description.key)
        event_type = value
        event_attributes = {}

        if value:
            if self.entity_description.event_type_conversion:
                event_type = self.entity_description.event_type_conversion(value)
            if self.entity_description.event_attributes_conversion:
                event_attributes = self.entity_description.event_attributes_conversion(
                    value
                )

        self._trigger_event(event_type, event_attributes)
        self.async_write_ha_state()

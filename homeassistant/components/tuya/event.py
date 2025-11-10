"""Support for Tuya event entities."""

from __future__ import annotations

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
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import DPCodeB64DecodeWrapper, DPCodeEnumWrapper, DPCodeWrapper

# All descriptions can be found here. Mostly the Enum data types in the
# default status set of each category (that don't have a set instruction)
# end up being events.
EVENTS: dict[DeviceCategory, tuple[EventEntityDescription, ...]] = {
    DeviceCategory.SP: (
        EventEntityDescription(
            key=DPCode.ALARM_MESSAGE,
            device_class=EventDeviceClass.DOORBELL,
            translation_key="alarm_message",
        ),
        EventEntityDescription(
            key=DPCode.DOORBELL_PIC,
            device_class=EventDeviceClass.DOORBELL,
            translation_key="doorbell_picture",
        ),
    ),
    DeviceCategory.WXKG: (
        EventEntityDescription(
            key=DPCode.SWITCH_MODE1,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "1"},
        ),
        EventEntityDescription(
            key=DPCode.SWITCH_MODE2,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "2"},
        ),
        EventEntityDescription(
            key=DPCode.SWITCH_MODE3,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "3"},
        ),
        EventEntityDescription(
            key=DPCode.SWITCH_MODE4,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "4"},
        ),
        EventEntityDescription(
            key=DPCode.SWITCH_MODE5,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "5"},
        ),
        EventEntityDescription(
            key=DPCode.SWITCH_MODE6,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "6"},
        ),
        EventEntityDescription(
            key=DPCode.SWITCH_MODE7,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "7"},
        ),
        EventEntityDescription(
            key=DPCode.SWITCH_MODE8,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "8"},
        ),
        EventEntityDescription(
            key=DPCode.SWITCH_MODE9,
            device_class=EventDeviceClass.BUTTON,
            translation_key="numbered_button",
            translation_placeholders={"button_number": "9"},
        ),
    ),
}


def _get_dpcode_wrapper(
    device: CustomerDevice,
    description: EventEntityDescription,
) -> DPCodeWrapper | None:
    """Get the appropriate DPCode wrapper for the event description.

    Try to find an enum wrapper first. If not found, try b64 decode wrapper.
    """
    # Try to get enum wrapper for DPType.ENUM
    if enum_wrapper := DPCodeEnumWrapper.find_dpcode(
        device, description.key, prefer_function=True
    ):
        return enum_wrapper

    # For RAW/STRING types, try to get a b64 decode wrapper
    if b64_wrapper := DPCodeB64DecodeWrapper.find_dpcode(
        device, description.key, prefer_function=True
    ):
        return b64_wrapper

    return None


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
                entities.extend(
                    TuyaEventEntity(
                        device, manager, description, dpcode_wrapper=dpcode_wrapper
                    )
                    for description in descriptions
                    if (dpcode_wrapper := _get_dpcode_wrapper(device, description))
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaEventEntity(TuyaEntity, EventEntity):
    """Tuya Event Entity."""

    entity_description: EventEntityDescription

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: EventEntityDescription,
        dpcode_wrapper: DPCodeWrapper,
    ) -> None:
        """Init Tuya event entity."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._dpcode_wrapper = dpcode_wrapper

        self._attr_event_types = ["dpcode_update"]
        if isinstance(dpcode_wrapper, DPCodeEnumWrapper):
            # Enum types have a range of valid values
            self._attr_event_types = dpcode_wrapper.type_information.range

    async def _handle_state_update(
        self,
        updated_status_properties: list[str] | None,
        dp_timestamps: dict | None = None,
    ) -> None:
        if (
            updated_status_properties is None
            or self._dpcode_wrapper.dpcode not in updated_status_properties
            or (value := self._dpcode_wrapper.read_device_status(self.device)) is None
        ):
            return

        event_type = "dpcode_update"
        event_attributes = {}
        if isinstance(self._dpcode_wrapper, DPCodeEnumWrapper):
            event_type = value
        else:
            event_attributes = {"value": value}

        self._trigger_event(event_type, event_attributes)
        self.async_write_ha_state()

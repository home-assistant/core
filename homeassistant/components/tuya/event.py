"""Support for Tuya event entities."""

from __future__ import annotations

from base64 import b64decode
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
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import (
    DeviceWrapper,
    DPCodeEnumWrapper,
    DPCodeRawWrapper,
    DPCodeStringWrapper,
    DPCodeTypeInformationWrapper,
)


class _EventEnumWrapper(DPCodeEnumWrapper):
    """Wrapper for event enum DP codes."""

    def read_device_status(self, device: CustomerDevice) -> tuple[str, None] | None:
        """Return the event details."""
        if (raw_value := super().read_device_status(device)) is None:
            return None
        return (raw_value, None)


class _AlarmMessageWrapper(DPCodeStringWrapper):
    """Wrapper for a STRING message on DPCode.ALARM_MESSAGE."""

    def __init__(self, dpcode: str, type_information: Any) -> None:
        """Init _AlarmMessageWrapper."""
        super().__init__(dpcode, type_information)
        self.options = ["triggered"]

    def read_device_status(
        self, device: CustomerDevice
    ) -> tuple[str, dict[str, Any]] | None:
        """Return the event attributes for the alarm message."""
        if (raw_value := super().read_device_status(device)) is None:
            return None
        return ("triggered", {"message": b64decode(raw_value).decode("utf-8")})


class _DoorbellPicWrapper(DPCodeRawWrapper):
    """Wrapper for a RAW message on DPCode.DOORBELL_PIC.

    It is expected that the RAW data is base64/utf8 encoded URL of the picture.
    """

    def __init__(self, dpcode: str, type_information: Any) -> None:
        """Init _DoorbellPicWrapper."""
        super().__init__(dpcode, type_information)
        self.options = ["triggered"]

    def read_device_status(
        self, device: CustomerDevice
    ) -> tuple[str, dict[str, Any]] | None:
        """Return the event attributes for the doorbell picture."""
        if (status := super().read_device_status(device)) is None:
            return None
        return ("triggered", {"message": status.decode("utf-8")})


@dataclass(frozen=True)
class TuyaEventEntityDescription(EventEntityDescription):
    """Describe a Tuya Event entity."""

    wrapper_class: type[DPCodeTypeInformationWrapper] = _EventEnumWrapper


# All descriptions can be found here. Mostly the Enum data types in the
# default status set of each category (that don't have a set instruction)
# end up being events.
EVENTS: dict[DeviceCategory, tuple[TuyaEventEntityDescription, ...]] = {
    DeviceCategory.SP: (
        TuyaEventEntityDescription(
            key=DPCode.ALARM_MESSAGE,
            device_class=EventDeviceClass.DOORBELL,
            translation_key="doorbell_message",
            wrapper_class=_AlarmMessageWrapper,
        ),
        TuyaEventEntityDescription(
            key=DPCode.DOORBELL_PIC,
            device_class=EventDeviceClass.DOORBELL,
            translation_key="doorbell_picture",
            wrapper_class=_DoorbellPicWrapper,
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
                entities.extend(
                    TuyaEventEntity(
                        device, manager, description, dpcode_wrapper=dpcode_wrapper
                    )
                    for description in descriptions
                    if (
                        dpcode_wrapper := description.wrapper_class.find_dpcode(
                            device, description.key
                        )
                    )
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
        dpcode_wrapper: DeviceWrapper[tuple[str, dict[str, Any] | None]],
    ) -> None:
        """Init Tuya event entity."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._dpcode_wrapper = dpcode_wrapper
        self._attr_event_types = dpcode_wrapper.options

    async def _process_device_update(
        self,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Called when Tuya device sends an update with updated properties.

        Returns True if the Home Assistant state should be written,
        or False if the state write should be skipped.
        """
        if self._dpcode_wrapper.skip_update(
            self.device, updated_status_properties, dp_timestamps
        ) or not (event_data := self._dpcode_wrapper.read_device_status(self.device)):
            return False

        event_type, event_attributes = event_data
        self._trigger_event(event_type, event_attributes)
        return True

"""Support for Tuya valves."""

from dataclasses import dataclass
from typing import override

from tuya_device_handlers.definition.valve import (
    ValveDefinition,
    get_default_definition,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .coordinator import TuyaConfigEntry
from .entity import TuyaEntity, TuyaEntityDescription, get_child_device_info


@dataclass(frozen=True)
class TuyaValveEntityDescription(TuyaEntityDescription, ValveEntityDescription):
    """Describes a Tuya valve entity."""


VALVES: dict[DeviceCategory, tuple[TuyaValveEntityDescription, ...]] = {
    DeviceCategory.SFKZQ: (
        TuyaValveEntityDescription(
            key=DPCode.SWITCH,
            translation_key="valve",
            device_class=ValveDeviceClass.WATER,
        ),
    ),
}


def _make_channel_condition(key_str: str):
    """Return a callable that checks if a channel DP is present in the device."""
    try:
        dp_member = DPCode(key_str)
    except ValueError:
        dp_member = None

    def _condition(device: CustomerDevice) -> bool:
        if key_str in device.status_range:
            return True
        if dp_member is not None and dp_member in device.status_range:
            return True
        return False

    return _condition


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
                dynamic_descriptions: list[TuyaValveEntityDescription] = []
                for status_key in device.status_range:
                    if isinstance(status_key, str) and status_key.startswith("switch_"):
                        try:
                            channel_index = int(status_key.split("_", 1)[1])
                        except ValueError:
                            continue
                        dynamic_descriptions.append(
                            TuyaValveEntityDescription(
                                key=status_key,
                                translation_key="valve",
                                device_class=ValveDeviceClass.WATER,
                                channel_index=channel_index,
                                channel_condition=_make_channel_condition(status_key),
                            )
                        )

                if dynamic_descriptions:
                    dynamic_descriptions.sort(key=lambda d: d.channel_index or 0)
                    descriptions_to_use = (*descriptions, *dynamic_descriptions)
                else:
                    descriptions_to_use = descriptions

                parent_device_id = dr.async_get_device_id_by_identifier(
                    hass, (DOMAIN, device.id), config_entry_id=entry.entry_id
                )
                entities.extend(
                    TuyaValveEntity(
                        device,
                        manager,
                        description,
                        definition,
                        device_info=get_child_device_info(
                            device, parent_device_id, description
                        ),
                    )
                    for description in descriptions_to_use
                    if (definition := get_default_definition(device, description.key))
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
        description: TuyaValveEntityDescription,
        definition: ValveDefinition,
        *,
        device_info: ChildDeviceInfo | None = None,
    ) -> None:
        """Init TuyaValveEntity."""
        super().__init__(device, device_manager, description, device_info=device_info)
        self._dpcode_wrapper = definition.control_wrapper

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the valve is closed."""
        if (is_open := self._read_wrapper(self._dpcode_wrapper)) is None:
            return None
        return not is_open

    @override
    async def _process_device_update(
        self,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Called when Tuya device sends an update with updated properties.

        Returns True if the Home Assistant state should be written,
        or False if the state write should be skipped.
        """
        return not self._dpcode_wrapper.skip_update(
            self.device, updated_status_properties, dp_timestamps
        )

    @override
    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, True)

    @override
    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self._async_send_wrapper_updates(self._dpcode_wrapper, False)

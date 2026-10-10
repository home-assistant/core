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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .coordinator import TuyaConfigEntry
from .entity import TuyaEntity, TuyaEntityDescription


@dataclass(frozen=True)
class TuyaValveEntityDescription(TuyaEntityDescription, ValveEntityDescription):
    """Describes a Tuya valve entity."""

    current_position: DPCode | tuple[DPCode, ...] | None = None


VALVES: dict[DeviceCategory, tuple[TuyaValveEntityDescription, ...]] = {
    DeviceCategory.SFKZQ: (
        TuyaValveEntityDescription(
            key=DPCode.SWITCH,
            translation_key="valve",
            device_class=ValveDeviceClass.WATER,
            current_position=DPCode.PERCENT_STATE,
        ),
        *(
            TuyaValveEntityDescription(
                key=DPCode(f"switch_{channel}"),
                translation_key="indexed_valve",
                translation_placeholders={"index": str(channel)},
                device_class=ValveDeviceClass.WATER,
            )
            for channel in range(1, 9)
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
                    TuyaValveEntity(device, manager, description, definition)
                    for description in descriptions
                    if (
                        definition := get_default_definition(
                            device,
                            description.key,
                            current_position_dpcode=description.current_position,
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
        description: TuyaValveEntityDescription,
        definition: ValveDefinition,
    ) -> None:
        """Init TuyaValveEntity."""
        super().__init__(device, device_manager, description)
        self._dpcode_wrapper = definition.control_wrapper
        self._current_position_wrapper = definition.current_position_wrapper
        self._attr_reports_position = self._current_position_wrapper is not None

    @property
    @override
    def current_valve_position(self) -> int | None:
        """Return the current position of the valve."""
        if self._current_position_wrapper is None:
            return None
        return self._read_wrapper(self._current_position_wrapper)

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
        if self._current_position_wrapper is not None and not (
            self._current_position_wrapper.skip_update(
                self.device, updated_status_properties, dp_timestamps
            )
        ):
            return True
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

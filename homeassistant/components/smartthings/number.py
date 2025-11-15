"""Support for number entities through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN, UNIT_MAP
from .entity import SmartThingsEntity
from .util import get_range_options_count


@dataclass(frozen=True, kw_only=True)
class SmartThingsNumberRangeEntityDescription(NumberEntityDescription):
    """Describe a SmartThings number range entity."""

    status_attribute: Attribute
    range_attribute: Attribute
    command: Command
    component_translation_key: dict[str, str] | None = None
    exists_fn: Callable[[FullDevice, str], bool] = lambda device, component: True


CAPABILITY_TO_NUMBER_RANGE_DESCRIPTIONS: dict[
    Capability, SmartThingsNumberRangeEntityDescription
] = {
    Capability.THERMOSTAT_COOLING_SETPOINT: SmartThingsNumberRangeEntityDescription(
        key=Capability.THERMOSTAT_COOLING_SETPOINT,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        status_attribute=Attribute.COOLING_SETPOINT,
        range_attribute=Attribute.COOLING_SETPOINT_RANGE,
        command=Command.SET_COOLING_SETPOINT,
        exists_fn=lambda device, component: component in ("cooler", "freezer"),
        component_translation_key={
            "cooler": "cooler_temperature",
            "freezer": "freezer_temperature",
        },
    ),
    Capability.SAMSUNG_CE_AUDIO_VOLUME_LEVEL: SmartThingsNumberRangeEntityDescription(
        key="audio_volume_level",
        entity_category=EntityCategory.CONFIG,
        status_attribute=Attribute.VOLUME_LEVEL,
        range_attribute=Attribute.VOLUME_LEVEL_RANGE,
        command=Command.SET_VOLUME_LEVEL,
        exists_fn=lambda device, component: (
            get_range_options_count(
                device,
                component,
                Capability.SAMSUNG_CE_AUDIO_VOLUME_LEVEL,
                Attribute.VOLUME_LEVEL_RANGE,
            )
            >= 2
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add number entities for a config entry."""
    entry_data = entry.runtime_data
    entities: list[NumberEntity] = [
        SmartThingsWasherRinseCyclesNumberEntity(entry_data.client, device)
        for device in entry_data.devices.values()
        if Capability.CUSTOM_WASHER_RINSE_CYCLES in device.status[MAIN]
    ]
    entities.extend(
        SmartThingsHoodNumberEntity(entry_data.client, device)
        for device in entry_data.devices.values()
        if (
            (hood_component := device.status.get("hood")) is not None
            and Capability.SAMSUNG_CE_HOOD_FAN_SPEED in hood_component
            and Capability.SAMSUNG_CE_CONNECTION_STATE not in hood_component
        )
    )

    entities.extend(
        SmartThingsRangeNumberEntity(
            entry_data.client,
            device,
            description,
            capability,
            component,
        )
        for device in entry_data.devices.values()
        for component in device.status
        for capability, description in CAPABILITY_TO_NUMBER_RANGE_DESCRIPTIONS.items()
        if capability in device.status[component]
        and description.exists_fn(device, component)
    )

    async_add_entities(entities)


class SmartThingsWasherRinseCyclesNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number."""

    _attr_translation_key = "washer_rinse_cycles"
    _attr_native_step = 1.0
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Initialize the instance."""
        super().__init__(client, device, {Capability.CUSTOM_WASHER_RINSE_CYCLES})
        self._attr_unique_id = f"{device.device.device_id}_{MAIN}_{Capability.CUSTOM_WASHER_RINSE_CYCLES}_{Attribute.WASHER_RINSE_CYCLES}_{Attribute.WASHER_RINSE_CYCLES}"

    @property
    def options(self) -> list[int]:
        """Return the list of options."""
        values = self.get_attribute_value(
            Capability.CUSTOM_WASHER_RINSE_CYCLES,
            Attribute.SUPPORTED_WASHER_RINSE_CYCLES,
        )
        return [int(value) for value in values] if values else []

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return int(
            self.get_attribute_value(
                Capability.CUSTOM_WASHER_RINSE_CYCLES, Attribute.WASHER_RINSE_CYCLES
            )
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return min(self.options)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return max(self.options)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            Capability.CUSTOM_WASHER_RINSE_CYCLES,
            Command.SET_WASHER_RINSE_CYCLES,
            str(int(value)),
        )


class SmartThingsHoodNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number."""

    _attr_translation_key = "hood_fan_speed"
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Initialize the instance."""
        super().__init__(
            client, device, {Capability.SAMSUNG_CE_HOOD_FAN_SPEED}, component="hood"
        )
        self._attr_unique_id = f"{device.device.device_id}_hood_{Capability.SAMSUNG_CE_HOOD_FAN_SPEED}_{Attribute.HOOD_FAN_SPEED}_{Attribute.HOOD_FAN_SPEED}"

    @property
    def options(self) -> list[int]:
        """Return the list of options."""
        min_value = self.get_attribute_value(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            Attribute.SETTABLE_MIN_FAN_SPEED,
        )
        max_value = self.get_attribute_value(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            Attribute.SETTABLE_MAX_FAN_SPEED,
        )
        return list(range(min_value, max_value + 1))

    @property
    def native_value(self) -> int:
        """Return the current value."""
        return int(
            self.get_attribute_value(
                Capability.SAMSUNG_CE_HOOD_FAN_SPEED, Attribute.HOOD_FAN_SPEED
            )
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return min(self.options)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return max(self.options)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            Command.SET_HOOD_FAN_SPEED,
            int(value),
        )


class SmartThingsRangeNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number."""

    entity_description: SmartThingsNumberRangeEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        description: SmartThingsNumberRangeEntityDescription,
        capability: Capability,
        component: str = MAIN,
    ) -> None:
        """Initialize the instance."""
        super().__init__(
            client,
            device,
            {capability},
            component=component,
        )
        self.entity_description = description
        self._attr_unique_id = f"{device.device.device_id}_{component}_{description.key}_{description.status_attribute}_{description.status_attribute}"
        unit = self._internal_state[capability][description.status_attribute].unit
        if unit is not None:
            self._attr_native_unit_of_measurement = UNIT_MAP[unit]
        self.number_capability = capability
        if description.component_translation_key:
            self._attr_translation_key = description.component_translation_key.get(
                component, description.key
            )
        else:
            self._attr_translation_key = description.key

    @property
    def range(self) -> dict[str, int]:
        """Return the list of options."""
        return self.get_attribute_value(
            self.number_capability,
            self.entity_description.range_attribute,
        )

    @property
    def native_value(self) -> int:
        """Return the current value."""
        return int(
            self.get_attribute_value(
                self.number_capability,
                self.entity_description.status_attribute,
            )
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.range["minimum"]

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.range["maximum"]

    @property
    def native_step(self) -> float:
        """Return the step value."""
        return self.range["step"]

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            self.number_capability,
            self.entity_description.command,
            int(value),
        )

"""The Flexit Nordic (BACnet) integration."""

import asyncio.exceptions
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FlexitCoordinator
from .const import DOMAIN
from .entity import FlexitEntity


@dataclass(kw_only=True, frozen=True)
class FlexitNumberEntityDescription(NumberEntityDescription):
    """Describes a Flexit number entity."""

    native_value_fn: Callable[[FlexitBACnet], float]
    set_native_value_fn: Callable[[FlexitBACnet], Callable[[int], Awaitable[None]]]


NUMBERS: tuple[FlexitNumberEntityDescription, ...] = (
    FlexitNumberEntityDescription(
        key="away_extract_fan_setpoint",
        translation_key="away_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_away,
        set_native_value_fn=lambda device: device.set_fan_setpoint_extract_air_away,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="away_supply_fan_setpoint",
        translation_key="away_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_away,
        set_native_value_fn=lambda device: device.set_fan_setpoint_supply_air_away,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="cooker_hood_extract_fan_setpoint",
        translation_key="cooker_hood_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_cooker,
        set_native_value_fn=lambda device: device.set_fan_setpoint_extract_air_cooker,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="cooker_hood_supply_fan_setpoint",
        translation_key="cooker_hood_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_cooker,
        set_native_value_fn=lambda device: device.set_fan_setpoint_supply_air_cooker,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="fireplace_extract_fan_setpoint",
        translation_key="fireplace_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_fire,
        set_native_value_fn=lambda device: device.set_fan_setpoint_extract_air_fire,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="fireplace_supply_fan_setpoint",
        translation_key="fireplace_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_fire,
        set_native_value_fn=lambda device: device.set_fan_setpoint_supply_air_fire,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="high_extract_fan_setpoint",
        translation_key="high_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_high,
        set_native_value_fn=lambda device: device.set_fan_setpoint_extract_air_high,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="high_supply_fan_setpoint",
        translation_key="high_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_high,
        set_native_value_fn=lambda device: device.set_fan_setpoint_supply_air_high,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="home_extract_fan_setpoint",
        translation_key="home_extract_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_extract_air_home,
        set_native_value_fn=lambda device: device.set_fan_setpoint_extract_air_home,
        native_unit_of_measurement=PERCENTAGE,
    ),
    FlexitNumberEntityDescription(
        key="home_supply_fan_setpoint",
        translation_key="home_supply_fan_setpoint",
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        native_value_fn=lambda device: device.fan_setpoint_supply_air_home,
        set_native_value_fn=lambda device: device.set_fan_setpoint_supply_air_home,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) number from a config entry."""
    coordinator: FlexitCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        FlexitNumber(coordinator, description) for description in NUMBERS
    )


class FlexitNumber(FlexitEntity, NumberEntity):
    """Representation of a Flexit Number."""

    entity_description: FlexitNumberEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitNumberEntityDescription,
    ) -> None:
        """Initialize Flexit (bacnet) number."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.device.serial_number}-{entity_description.key}"
        )

    @property
    def native_value(self) -> float:
        """Return the state of the number."""
        return self.entity_description.native_value_fn(self.coordinator.device)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        set_native_value_fn = self.entity_description.set_native_value_fn(
            self.coordinator.device
        )
        try:
            await set_native_value_fn(int(value))
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
        finally:
            await self.coordinator.async_refresh()

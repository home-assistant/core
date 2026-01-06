"""Support for LetPot select entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from letpot.deviceclient import LetPotDeviceClient
from letpot.models import DeviceFeature, LightMode, TemperatureUnit

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LetPotConfigEntry, LetPotDeviceCoordinator
from .entity import LetPotEntity, LetPotEntityDescription, exception_handler

# Each change pushes a 'full' device status with the change. The library will cache
# pending changes to avoid overwriting, but try to avoid a lot of parallelism.
PARALLEL_UPDATES = 1


class LightBrightnessLowHigh(StrEnum):
    """Light brightness low/high model."""

    LOW = "low"
    HIGH = "high"


def _get_brightness_low_high_value(coordinator: LetPotDeviceCoordinator) -> str | None:
    """Return brightness as low/high for a device which only has a low and high value."""
    brightness = coordinator.data.light_brightness
    levels = coordinator.device_client.get_light_brightness_levels(
        coordinator.device.serial_number
    )
    return (
        LightBrightnessLowHigh.LOW.value
        if levels[0] == brightness
        else LightBrightnessLowHigh.HIGH.value
    )


async def _set_brightness_low_high_value(
    device_client: LetPotDeviceClient, serial: str, option: str
) -> None:
    """Set brightness from low/high for a device which only has a low and high value."""
    levels = device_client.get_light_brightness_levels(serial)
    await device_client.set_light_brightness(
        serial, levels[0] if option == LightBrightnessLowHigh.LOW.value else levels[1]
    )


@dataclass(frozen=True, kw_only=True)
class LetPotSelectEntityDescription(LetPotEntityDescription, SelectEntityDescription):
    """Describes a LetPot select entity."""

    value_fn: Callable[[LetPotDeviceCoordinator], str | None]
    set_value_fn: Callable[[LetPotDeviceClient, str, str], Coroutine[Any, Any, None]]


SELECTORS: tuple[LetPotSelectEntityDescription, ...] = (
    LetPotSelectEntityDescription(
        key="display_temperature_unit",
        translation_key="display_temperature_unit",
        options=[x.name.lower() for x in TemperatureUnit],
        value_fn=(
            lambda coordinator: coordinator.data.temperature_unit.name.lower()
            if coordinator.data.temperature_unit is not None
            else None
        ),
        set_value_fn=(
            lambda device_client, serial, option: device_client.set_temperature_unit(
                serial, TemperatureUnit[option.upper()]
            )
        ),
        supported_fn=(
            lambda coordinator: DeviceFeature.TEMPERATURE_SET_UNIT
            in coordinator.device_client.device_info(
                coordinator.device.serial_number
            ).features
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    LetPotSelectEntityDescription(
        key="light_brightness_low_high",
        translation_key="light_brightness",
        options=[
            LightBrightnessLowHigh.LOW.value,
            LightBrightnessLowHigh.HIGH.value,
        ],
        value_fn=_get_brightness_low_high_value,
        set_value_fn=_set_brightness_low_high_value,
        supported_fn=(
            lambda coordinator: DeviceFeature.LIGHT_BRIGHTNESS_LOW_HIGH
            in coordinator.device_client.device_info(
                coordinator.device.serial_number
            ).features
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    LetPotSelectEntityDescription(
        key="light_mode",
        translation_key="light_mode",
        options=[x.name.lower() for x in LightMode],
        value_fn=(
            lambda coordinator: coordinator.data.light_mode.name.lower()
            if coordinator.data.light_mode is not None
            else None
        ),
        set_value_fn=(
            lambda device_client, serial, option: device_client.set_light_mode(
                serial, LightMode[option.upper()]
            )
        ),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LetPotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LetPot select entities based on a config entry and device status/features."""
    coordinators = entry.runtime_data
    async_add_entities(
        LetPotSelectEntity(coordinator, description)
        for description in SELECTORS
        for coordinator in coordinators
        if description.supported_fn(coordinator)
    )


class LetPotSelectEntity(LetPotEntity, SelectEntity):
    """Defines a LetPot select entity."""

    entity_description: LetPotSelectEntityDescription

    def __init__(
        self,
        coordinator: LetPotDeviceCoordinator,
        description: LetPotSelectEntityDescription,
    ) -> None:
        """Initialize LetPot select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{coordinator.device.serial_number}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option."""
        return self.entity_description.value_fn(self.coordinator)

    @exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        return await self.entity_description.set_value_fn(
            self.coordinator.device_client,
            self.coordinator.device.serial_number,
            option,
        )

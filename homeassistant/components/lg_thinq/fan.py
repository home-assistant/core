"""Support for fan entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity


@dataclass(frozen=True, kw_only=True)
class ThinQFanEntityDescription(FanEntityDescription):
    """Describes ThinQ fan entity."""

    operation_key: str
    preset_modes: list[str] | None = None


HOOD_FAN_DESC = FanEntityDescription(
    key=ThinQProperty.FAN_SPEED,
    translation_key=ThinQProperty.FAN_SPEED,
)

DEVICE_TYPE_FAN_MAP: dict[DeviceType, tuple[ThinQFanEntityDescription, ...]] = {
    DeviceType.CEILING_FAN: (
        ThinQFanEntityDescription(
            key=ThinQProperty.WIND_STRENGTH,
            name=None,
            operation_key=ThinQProperty.CEILING_FAN_OPERATION_MODE,
        ),
    ),
    DeviceType.VENTILATOR: (
        ThinQFanEntityDescription(
            key=ThinQProperty.WIND_STRENGTH,
            name=None,
            translation_key=ThinQProperty.WIND_STRENGTH,
            operation_key=ThinQProperty.VENTILATOR_OPERATION_MODE,
            preset_modes=["auto"],
        ),
    ),
}

HOOD_DEVICE_TYPES: set[DeviceType] = {DeviceType.HOOD, DeviceType.MICROWAVE_OVEN}

ORDERED_NAMED_FAN_SPEEDS = ["low", "mid", "high", "turbo", "power"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for fan platform."""
    entities: list[ThinQFanEntity | ThinQHoodFanEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        device_type = coordinator.api.device.device_type

        # Handle hood-type devices with numeric fan speed
        if device_type in HOOD_DEVICE_TYPES:
            entities.extend(
                ThinQHoodFanEntity(coordinator, HOOD_FAN_DESC, property_id)
                for property_id in coordinator.api.get_active_idx(
                    HOOD_FAN_DESC.key, ActiveMode.READ_WRITE
                )
            )
        # Handle other fan devices with named speeds
        elif (descriptions := DEVICE_TYPE_FAN_MAP.get(device_type)) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQFanEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(
                        description.key, ActiveMode.READ_WRITE
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQFanEntity(ThinQEntity, FanEntity):
    """Represent a thinq fan platform."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: ThinQFanEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize fan platform."""
        super().__init__(coordinator, entity_description, property_id)

        self._ordered_named_fan_speeds = ORDERED_NAMED_FAN_SPEEDS.copy()
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        self._attr_preset_modes = []
        for option in self.data.options:
            if (
                entity_description.preset_modes is not None
                and option in entity_description.preset_modes
            ):
                self._attr_supported_features |= FanEntityFeature.PRESET_MODE
                self._attr_preset_modes.append(option)
            else:
                for ordered_step in ORDERED_NAMED_FAN_SPEEDS:
                    if (
                        ordered_step in self._ordered_named_fan_speeds
                        and ordered_step not in self.data.options
                    ):
                        self._ordered_named_fan_speeds.remove(ordered_step)
        self._attr_speed_count = len(self._ordered_named_fan_speeds)
        self._operation_id = entity_description.operation_key

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        # Update power on state.
        self._attr_is_on = _is_on = self.coordinator.data[self._operation_id].is_on

        # Update fan speed.
        if _is_on and (mode := self.data.value) is not None:
            if self.preset_modes is not None and mode in self.preset_modes:
                self._attr_preset_mode = mode
                self._attr_percentage = 0
            elif mode in self._ordered_named_fan_speeds:
                self._attr_percentage = ordered_list_item_to_percentage(
                    self._ordered_named_fan_speeds, mode
                )
                self._attr_preset_mode = None
        else:
            self._attr_preset_mode = None
            self._attr_percentage = 0

        _LOGGER.debug(
            "[%s:%s] update status: is_on=%s, percentage=%s, preset_mode=%s",
            self.coordinator.device_name,
            self.property_id,
            _is_on,
            self.percentage,
            self.preset_mode,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug(
            "[%s:%s] async_set_preset_mode. preset_mode=%s",
            self.coordinator.device_name,
            self.property_id,
            preset_mode,
        )
        await self.async_call_api(
            self.coordinator.api.post(self.property_id, preset_mode)
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return
        try:
            value = percentage_to_ordered_list_item(
                self._ordered_named_fan_speeds, percentage
            )
        except ValueError:
            _LOGGER.exception("Failed to async_set_percentage")
            return

        _LOGGER.debug(
            "[%s:%s] async_set_percentage. percentage=%s, value=%s",
            self.coordinator.device_name,
            self.property_id,
            percentage,
            value,
        )
        await self.async_call_api(self.coordinator.api.post(self.property_id, value))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug(
            "[%s:%s] async_turn_on percentage=%s, preset_mode=%s, kwargs=%s",
            self.coordinator.device_name,
            self._operation_id,
            percentage,
            preset_mode,
            kwargs,
        )
        await self.async_call_api(
            self.coordinator.api.async_turn_on(self._operation_id)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        _LOGGER.debug(
            "[%s:%s] async_turn_off kwargs=%s",
            self.coordinator.device_name,
            self._operation_id,
            kwargs,
        )
        await self.async_call_api(
            self.coordinator.api.async_turn_off(self._operation_id)
        )


class ThinQHoodFanEntity(ThinQEntity, FanEntity):
    """Represent a thinq hood fan platform.

    Hood fans use numeric speed values (e.g., 0=off, 1=low, 2=high)
    rather than named speed presets.
    """

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: FanEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize hood fan platform."""
        super().__init__(coordinator, entity_description, property_id)

        # Get min/max from data, default to 0-2 if not available
        self._min_speed: int = int(self.data.min) if self.data.min is not None else 0
        self._max_speed: int = int(self.data.max) if self.data.max is not None else 2

        # Speed count is the number of non-zero speeds
        self._attr_speed_count = self._max_speed - self._min_speed

    @property
    def _speed_range(self) -> tuple[int, int]:
        """Return the speed range excluding off (0)."""
        return (self._min_speed + 1, self._max_speed)

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        # Update min/max if available from data
        if self.data.min is not None:
            self._min_speed = int(self.data.min)
        if self.data.max is not None:
            self._max_speed = int(self.data.max)
            self._attr_speed_count = self._max_speed - self._min_speed

        # Get current speed value
        current_speed = self.data.value
        if current_speed is None or current_speed == self._min_speed:
            self._attr_is_on = False
            self._attr_percentage = 0
        else:
            self._attr_is_on = True
            self._attr_percentage = ranged_value_to_percentage(
                self._speed_range, current_speed
            )

        _LOGGER.debug(
            "[%s:%s] update status: is_on=%s, percentage=%s, speed=%s, min=%s, max=%s",
            self.coordinator.device_name,
            self.property_id,
            self.is_on,
            self.percentage,
            current_speed,
            self._min_speed,
            self._max_speed,
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = round(percentage_to_ranged_value(self._speed_range, percentage))

        _LOGGER.debug(
            "[%s:%s] async_set_percentage: percentage=%s -> speed=%s",
            self.coordinator.device_name,
            self.property_id,
            percentage,
            speed,
        )
        await self.async_call_api(self.coordinator.api.post(self.property_id, speed))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

        # Default to lowest non-zero speed
        speed = self._min_speed + 1
        _LOGGER.debug(
            "[%s:%s] async_turn_on: speed=%s",
            self.coordinator.device_name,
            self.property_id,
            speed,
        )
        await self.async_call_api(self.coordinator.api.post(self.property_id, speed))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        _LOGGER.debug(
            "[%s:%s] async_turn_off",
            self.coordinator.device_name,
            self.property_id,
        )
        await self.async_call_api(
            self.coordinator.api.post(self.property_id, self._min_speed)
        )

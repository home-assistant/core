"""Support for number entities."""

from __future__ import annotations

import logging

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode, TimerProperty

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity

NUMBER_DESC: dict[ThinQProperty, NumberEntityDescription] = {
    ThinQProperty.FAN_SPEED: NumberEntityDescription(
        key=ThinQProperty.FAN_SPEED,
        translation_key=ThinQProperty.FAN_SPEED,
    ),
    ThinQProperty.LAMP_BRIGHTNESS: NumberEntityDescription(
        key=ThinQProperty.LAMP_BRIGHTNESS,
        translation_key=ThinQProperty.LAMP_BRIGHTNESS,
    ),
    ThinQProperty.LIGHT_STATUS: NumberEntityDescription(
        key=ThinQProperty.LIGHT_STATUS,
        native_unit_of_measurement=PERCENTAGE,
        translation_key=ThinQProperty.LIGHT_STATUS,
    ),
    ThinQProperty.TARGET_HUMIDITY: NumberEntityDescription(
        key=ThinQProperty.TARGET_HUMIDITY,
        device_class=NumberDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        translation_key=ThinQProperty.TARGET_HUMIDITY,
    ),
    ThinQProperty.TARGET_TEMPERATURE: NumberEntityDescription(
        key=ThinQProperty.TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key=ThinQProperty.TARGET_TEMPERATURE,
    ),
    ThinQProperty.WIND_TEMPERATURE: NumberEntityDescription(
        key=ThinQProperty.WIND_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key=ThinQProperty.WIND_TEMPERATURE,
    ),
}
TIMER_NUMBER_DESC: dict[ThinQProperty, NumberEntityDescription] = {
    ThinQProperty.RELATIVE_HOUR_TO_START: NumberEntityDescription(
        key=ThinQProperty.RELATIVE_HOUR_TO_START,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=ThinQProperty.RELATIVE_HOUR_TO_START,
    ),
    TimerProperty.RELATIVE_HOUR_TO_START_WM: NumberEntityDescription(
        key=ThinQProperty.RELATIVE_HOUR_TO_START,
        native_min_value=0,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=TimerProperty.RELATIVE_HOUR_TO_START_WM,
    ),
    ThinQProperty.RELATIVE_HOUR_TO_STOP: NumberEntityDescription(
        key=ThinQProperty.RELATIVE_HOUR_TO_STOP,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=ThinQProperty.RELATIVE_HOUR_TO_STOP,
    ),
    TimerProperty.RELATIVE_HOUR_TO_STOP_WM: NumberEntityDescription(
        key=ThinQProperty.RELATIVE_HOUR_TO_STOP,
        native_min_value=0,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=TimerProperty.RELATIVE_HOUR_TO_STOP_WM,
    ),
    ThinQProperty.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP: NumberEntityDescription(
        key=ThinQProperty.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=ThinQProperty.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP,
    ),
}
WASHER_NUMBERS: tuple[NumberEntityDescription, ...] = (
    TIMER_NUMBER_DESC[TimerProperty.RELATIVE_HOUR_TO_START_WM],
    TIMER_NUMBER_DESC[TimerProperty.RELATIVE_HOUR_TO_STOP_WM],
)

DEVICE_TYPE_NUMBER_MAP: dict[DeviceType, tuple[NumberEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        TIMER_NUMBER_DESC[ThinQProperty.RELATIVE_HOUR_TO_START],
        TIMER_NUMBER_DESC[ThinQProperty.RELATIVE_HOUR_TO_STOP],
        TIMER_NUMBER_DESC[ThinQProperty.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP],
    ),
    DeviceType.AIR_PURIFIER_FAN: (
        NUMBER_DESC[ThinQProperty.WIND_TEMPERATURE],
        TIMER_NUMBER_DESC[ThinQProperty.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP],
    ),
    DeviceType.DRYER: WASHER_NUMBERS,
    DeviceType.HOOD: (
        NUMBER_DESC[ThinQProperty.LAMP_BRIGHTNESS],
        NUMBER_DESC[ThinQProperty.FAN_SPEED],
    ),
    DeviceType.HUMIDIFIER: (
        NUMBER_DESC[ThinQProperty.TARGET_HUMIDITY],
        TIMER_NUMBER_DESC[ThinQProperty.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP],
    ),
    DeviceType.MICROWAVE_OVEN: (
        NUMBER_DESC[ThinQProperty.LAMP_BRIGHTNESS],
        NUMBER_DESC[ThinQProperty.FAN_SPEED],
    ),
    DeviceType.OVEN: (NUMBER_DESC[ThinQProperty.TARGET_TEMPERATURE],),
    DeviceType.REFRIGERATOR: (NUMBER_DESC[ThinQProperty.TARGET_TEMPERATURE],),
    DeviceType.STYLER: (TIMER_NUMBER_DESC[TimerProperty.RELATIVE_HOUR_TO_STOP_WM],),
    DeviceType.WASHCOMBO_MAIN: WASHER_NUMBERS,
    DeviceType.WASHCOMBO_MINI: WASHER_NUMBERS,
    DeviceType.WASHER: WASHER_NUMBERS,
    DeviceType.WASHTOWER_DRYER: WASHER_NUMBERS,
    DeviceType.WASHTOWER: WASHER_NUMBERS,
    DeviceType.WASHTOWER_WASHER: WASHER_NUMBERS,
    DeviceType.WATER_HEATER: (
        NumberEntityDescription(
            key=ThinQProperty.TARGET_TEMPERATURE,
            native_max_value=60,
            native_min_value=35,
            native_step=1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            translation_key=ThinQProperty.TARGET_TEMPERATURE,
        ),
    ),
    DeviceType.WINE_CELLAR: (
        NUMBER_DESC[ThinQProperty.LIGHT_STATUS],
        NUMBER_DESC[ThinQProperty.TARGET_TEMPERATURE],
    ),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for number platform."""
    entities: list[ThinQNumberEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_NUMBER_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQNumberEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(
                        description.key, ActiveMode.READ_WRITE
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQNumberEntity(ThinQEntity, NumberEntity):
    """Represent a thinq number platform."""

    _attr_mode = NumberMode.BOX

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        self._attr_native_value = self.data.value

        # Update unit.
        if (
            unit_of_measurement := self._get_unit_of_measurement(self.data.unit)
        ) is not None:
            self._attr_native_unit_of_measurement = unit_of_measurement

        # Undate range.
        if (
            self.entity_description.native_min_value is None
            and (min_value := self.data.min) is not None
        ):
            self._attr_native_min_value = min_value

        if (
            self.entity_description.native_max_value is None
            and (max_value := self.data.max) is not None
        ):
            self._attr_native_max_value = max_value

        if (
            self.entity_description.native_step is None
            and (step := self.data.step) is not None
        ):
            self._attr_native_step = step

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s, unit:%s, min:%s, max:%s, step:%s",
            self.coordinator.device_name,
            self.property_id,
            self.data.value,
            self.native_value,
            self.native_unit_of_measurement,
            self.native_min_value,
            self.native_max_value,
            self.native_step,
        )

    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        if self.step.is_integer():
            value = int(value)
        _LOGGER.debug(
            "[%s:%s] async_set_native_value: %s",
            self.coordinator.device_name,
            self.property_id,
            value,
        )

        await self.async_call_api(self.coordinator.api.post(self.property_id, value))

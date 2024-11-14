"""Platform for eq3 number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from eq3btsmart import Thermostat
from eq3btsmart.const import (
    EQ3BT_MAX_OFFSET,
    EQ3BT_MAX_TEMP,
    EQ3BT_MIN_OFFSET,
    EQ3BT_MIN_TEMP,
)
from eq3btsmart.models import Presets

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Eq3ConfigEntry
from .const import (
    ENTITY_KEY_COMFORT,
    ENTITY_KEY_ECO,
    ENTITY_KEY_OFFSET,
    ENTITY_KEY_WINDOW_OPEN_TEMPERATURE,
    ENTITY_KEY_WINDOW_OPEN_TIMEOUT,
    EQ3BT_STEP,
)
from .entity import Eq3Entity


@dataclass(frozen=True, kw_only=True)
class Eq3NumberEntityDescription(NumberEntityDescription):
    """Entity description for eq3 number entities."""

    value_func: Callable[[Presets], float]
    value_set_func: Callable[
        [Thermostat],
        Callable[[float], Awaitable[None]],
    ]
    mode: NumberMode = NumberMode.BOX
    entity_category: EntityCategory | None = EntityCategory.CONFIG


NUMBER_ENTITY_DESCRIPTIONS = [
    Eq3NumberEntityDescription(
        key=ENTITY_KEY_COMFORT,
        value_func=lambda presets: presets.comfort_temperature.value,
        value_set_func=lambda thermostat: thermostat.async_configure_comfort_temperature,
        translation_key=ENTITY_KEY_COMFORT,
        native_min_value=EQ3BT_MIN_TEMP,
        native_max_value=EQ3BT_MAX_TEMP,
        native_step=EQ3BT_STEP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    Eq3NumberEntityDescription(
        key=ENTITY_KEY_ECO,
        value_func=lambda presets: presets.eco_temperature.value,
        value_set_func=lambda thermostat: thermostat.async_configure_eco_temperature,
        translation_key=ENTITY_KEY_ECO,
        native_min_value=EQ3BT_MIN_TEMP,
        native_max_value=EQ3BT_MAX_TEMP,
        native_step=EQ3BT_STEP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    Eq3NumberEntityDescription(
        key=ENTITY_KEY_WINDOW_OPEN_TEMPERATURE,
        value_func=lambda presets: presets.window_open_temperature.value,
        value_set_func=lambda thermostat: thermostat.async_configure_window_open_temperature,
        translation_key=ENTITY_KEY_WINDOW_OPEN_TEMPERATURE,
        native_min_value=EQ3BT_MIN_TEMP,
        native_max_value=EQ3BT_MAX_TEMP,
        native_step=EQ3BT_STEP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    Eq3NumberEntityDescription(
        key=ENTITY_KEY_OFFSET,
        value_func=lambda presets: presets.offset_temperature.value,
        value_set_func=lambda thermostat: thermostat.async_configure_temperature_offset,
        translation_key=ENTITY_KEY_OFFSET,
        native_min_value=EQ3BT_MIN_OFFSET,
        native_max_value=EQ3BT_MAX_OFFSET,
        native_step=EQ3BT_STEP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    Eq3NumberEntityDescription(
        key=ENTITY_KEY_WINDOW_OPEN_TIMEOUT,
        value_set_func=lambda thermostat: thermostat.async_configure_window_open_duration,
        value_func=lambda presets: presets.window_open_time.value.total_seconds() / 60,
        translation_key=ENTITY_KEY_WINDOW_OPEN_TIMEOUT,
        native_min_value=0,
        native_max_value=60,
        native_step=5,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry."""

    async_add_entities(
        Eq3NumberEntity(entry, entity_description)
        for entity_description in NUMBER_ENTITY_DESCRIPTIONS
    )


class Eq3NumberEntity(Eq3Entity, NumberEntity):
    """Base class for all eq3 number entities."""

    entity_description: Eq3NumberEntityDescription

    def __init__(
        self, entry: Eq3ConfigEntry, entity_description: Eq3NumberEntityDescription
    ) -> None:
        """Initialize the entity."""

        super().__init__(entry, entity_description.key)
        self.entity_description = entity_description

    @property
    def native_value(self) -> float:
        """Return the state of the entity."""

        if TYPE_CHECKING:
            assert self._thermostat.status is not None
            assert self._thermostat.status.presets is not None

        return self.entity_description.value_func(self._thermostat.status.presets)

    async def async_set_native_value(self, value: float) -> None:
        """Set the state of the entity."""

        await self.entity_description.value_set_func(self._thermostat)(value)

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""

        return (
            self._thermostat.status is not None
            and self._thermostat.status.presets is not None
            and self._attr_available
        )

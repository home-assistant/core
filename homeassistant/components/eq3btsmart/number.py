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
    DOMAIN as NUMBER_DOMAIN,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_MAC_ADDRESS,
    DOMAIN,
    ENTITY_KEY_AWAY_HOURS,
    ENTITY_KEY_AWAY_TEMPERATURE,
    ENTITY_KEY_COMFORT,
    ENTITY_KEY_ECO,
    ENTITY_KEY_OFFSET,
    ENTITY_KEY_WINDOW_OPEN_TEMPERATURE,
    ENTITY_KEY_WINDOW_OPEN_TIMEOUT,
    EQ3BT_STEP,
    MIN_FIRMWARE_FOR_PRESETS,
)
from .coordinator import Eq3ConfigEntry
from .entity import Eq3Entity


@dataclass(frozen=True, kw_only=True)
class Eq3NumberEntityDescription(NumberEntityDescription):
    """Entity description for eq3 number entities."""

    value_set_func: Callable[
        [Thermostat],
        Callable[[float], Awaitable[None]],
    ]
    device_class: NumberDeviceClass | None = NumberDeviceClass.TEMPERATURE
    native_unit_of_measurement: str = UnitOfTemperature.CELSIUS
    native_min_value: float = EQ3BT_MIN_TEMP
    native_max_value: float = EQ3BT_MAX_TEMP
    native_step: float = EQ3BT_STEP
    mode: NumberMode = NumberMode.BOX
    entity_category: EntityCategory | None = EntityCategory.CONFIG


@dataclass(frozen=True, kw_only=True)
class Eq3PresetNumberEntityDescription(Eq3NumberEntityDescription):
    """Entity description for eq3 preset number entities."""

    value_func: Callable[[Presets], float]


NUMBER_ENTITY_DESCRIPTIONS = [
    Eq3NumberEntityDescription(
        key=ENTITY_KEY_AWAY_TEMPERATURE,
        value_set_func=lambda thermostat: thermostat.async_configure_away_temperature,
        translation_key=ENTITY_KEY_AWAY_TEMPERATURE,
    ),
    Eq3NumberEntityDescription(
        key=ENTITY_KEY_AWAY_HOURS,
        value_set_func=lambda thermostat: thermostat.async_configure_away_hours,
        translation_key=ENTITY_KEY_AWAY_HOURS,
        device_class=None,
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=0.5,
        native_max_value=1000000,
    ),
]


PRESET_NUMBER_ENTITY_DESCRIPTIONS = [
    Eq3PresetNumberEntityDescription(
        key=ENTITY_KEY_COMFORT,
        value_func=lambda presets: presets.comfort_temperature.value,
        value_set_func=lambda thermostat: thermostat.async_configure_comfort_temperature,
        translation_key=ENTITY_KEY_COMFORT,
    ),
    Eq3PresetNumberEntityDescription(
        key=ENTITY_KEY_ECO,
        value_func=lambda presets: presets.eco_temperature.value,
        value_set_func=lambda thermostat: thermostat.async_configure_eco_temperature,
        translation_key=ENTITY_KEY_ECO,
    ),
    Eq3PresetNumberEntityDescription(
        key=ENTITY_KEY_WINDOW_OPEN_TEMPERATURE,
        value_func=lambda presets: presets.window_open_temperature.value,
        value_set_func=lambda thermostat: thermostat.async_configure_window_open_temperature,
        translation_key=ENTITY_KEY_WINDOW_OPEN_TEMPERATURE,
    ),
    Eq3PresetNumberEntityDescription(
        key=ENTITY_KEY_OFFSET,
        value_func=lambda presets: presets.offset_temperature.value,
        value_set_func=lambda thermostat: thermostat.async_configure_temperature_offset,
        translation_key=ENTITY_KEY_OFFSET,
        native_min_value=EQ3BT_MIN_OFFSET,
        native_max_value=EQ3BT_MAX_OFFSET,
    ),
    Eq3PresetNumberEntityDescription(
        key=ENTITY_KEY_WINDOW_OPEN_TIMEOUT,
        value_set_func=lambda thermostat: thermostat.async_configure_window_open_duration,
        value_func=lambda presets: presets.window_open_time.value.total_seconds() / 60,
        translation_key=ENTITY_KEY_WINDOW_OPEN_TIMEOUT,
        device_class=None,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=0,
        native_max_value=60,
        native_step=5,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry."""

    mac_address: str = entry.data[CONF_MAC_ADDRESS]
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, mac_address)},
    )

    entities_to_add: list[NumberEntity] = [
        Eq3NumberEntity(entry, entity_description)
        for entity_description in NUMBER_ENTITY_DESCRIPTIONS
    ]

    if (
        device := device_registry.async_get_device(
            connections={(dr.CONNECTION_BLUETOOTH, mac_address)},
        )
    ) and (not device.sw_version or int(device.sw_version) < MIN_FIRMWARE_FOR_PRESETS):
        entity_registry = er.async_get(hass)

        for entity_description in PRESET_NUMBER_ENTITY_DESCRIPTIONS:
            unique_id = f"{mac_address}_{entity_description.key}"
            if entity_id := entity_registry.async_get_entity_id(
                NUMBER_DOMAIN, DOMAIN, unique_id
            ):
                entity_registry.async_remove(entity_id)
    else:
        entities_to_add += [
            Eq3PresetNumberEntity(entry, entity_description)
            for entity_description in PRESET_NUMBER_ENTITY_DESCRIPTIONS
        ]

    async_add_entities(entities_to_add)


class Eq3NumberEntity(Eq3Entity, RestoreNumber):
    """Base class for all eq3 number entities that should be restored."""

    entity_description: Eq3NumberEntityDescription

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        entity_description: Eq3NumberEntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(entry, entity_description.key)
        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Restore last state."""

        await super().async_added_to_hass()

        if (
            last_number_data := await self.async_get_last_number_data()
        ) and last_number_data.native_value is not None:
            await self.async_set_native_value(last_number_data.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the state of the entity."""

        self._attr_native_value = value
        await self.entity_description.value_set_func(self._thermostat)(value)


class Eq3PresetNumberEntity(Eq3Entity, NumberEntity):
    """Base class for all eq3 number entities."""

    entity_description: Eq3PresetNumberEntityDescription

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        entity_description: Eq3PresetNumberEntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(entry, entity_description.key)
        self.entity_description = entity_description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if TYPE_CHECKING:
            assert self._status.presets is not None

        self._attr_native_value = self.entity_description.value_func(
            self._status.presets
        )
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the state of the entity."""

        await self.entity_description.value_set_func(self._thermostat)(value)

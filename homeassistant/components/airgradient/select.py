"""Support for AirGradient select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from airgradient import AirGradientClient, Config
from airgradient.models import ConfigurationControl, LedBarMode, TemperatureUnit

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirGradientConfigEntry
from .const import DOMAIN, PM_STANDARD, PM_STANDARD_REVERSE
from .coordinator import AirGradientCoordinator
from .entity import AirGradientEntity


@dataclass(frozen=True, kw_only=True)
class AirGradientSelectEntityDescription(SelectEntityDescription):
    """Describes AirGradient select entity."""

    value_fn: Callable[[Config], str | None]
    set_value_fn: Callable[[AirGradientClient, str], Awaitable[None]]


CONFIG_CONTROL_ENTITY = AirGradientSelectEntityDescription(
    key="configuration_control",
    translation_key="configuration_control",
    options=[ConfigurationControl.CLOUD.value, ConfigurationControl.LOCAL.value],
    entity_category=EntityCategory.CONFIG,
    value_fn=lambda config: (
        config.configuration_control
        if config.configuration_control is not ConfigurationControl.NOT_INITIALIZED
        else None
    ),
    set_value_fn=lambda client, value: client.set_configuration_control(
        ConfigurationControl(value)
    ),
)

DISPLAY_SELECT_TYPES: tuple[AirGradientSelectEntityDescription, ...] = (
    AirGradientSelectEntityDescription(
        key="display_temperature_unit",
        translation_key="display_temperature_unit",
        options=[x.value for x in TemperatureUnit],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.temperature_unit,
        set_value_fn=lambda client, value: client.set_temperature_unit(
            TemperatureUnit(value)
        ),
    ),
    AirGradientSelectEntityDescription(
        key="display_pm_standard",
        translation_key="display_pm_standard",
        options=list(PM_STANDARD_REVERSE),
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: PM_STANDARD.get(config.pm_standard),
        set_value_fn=lambda client, value: client.set_pm_standard(
            PM_STANDARD_REVERSE[value]
        ),
    ),
)

LED_BAR_ENTITIES: tuple[AirGradientSelectEntityDescription, ...] = (
    AirGradientSelectEntityDescription(
        key="led_bar_mode",
        translation_key="led_bar_mode",
        options=[x.value for x in LedBarMode],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.led_bar_mode,
        set_value_fn=lambda client, value: client.set_led_bar_mode(LedBarMode(value)),
    ),
)

LEARNING_TIME_OFFSET_OPTIONS = [
    "12",
    "60",
    "120",
    "360",
    "720",
]

ABC_DAYS = [
    "1",
    "8",
    "30",
    "90",
    "180",
    "0",
]


def _get_value(value: int, values: list[str]) -> str | None:
    str_value = str(value)
    return str_value if str_value in values else None


CONTROL_ENTITIES: tuple[AirGradientSelectEntityDescription, ...] = (
    AirGradientSelectEntityDescription(
        key="nox_index_learning_time_offset",
        translation_key="nox_index_learning_time_offset",
        options=LEARNING_TIME_OFFSET_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: _get_value(
            config.nox_learning_offset, LEARNING_TIME_OFFSET_OPTIONS
        ),
        set_value_fn=lambda client, value: client.set_nox_learning_offset(int(value)),
    ),
    AirGradientSelectEntityDescription(
        key="voc_index_learning_time_offset",
        translation_key="voc_index_learning_time_offset",
        options=LEARNING_TIME_OFFSET_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: _get_value(
            config.tvoc_learning_offset, LEARNING_TIME_OFFSET_OPTIONS
        ),
        set_value_fn=lambda client, value: client.set_tvoc_learning_offset(int(value)),
    ),
    AirGradientSelectEntityDescription(
        key="co2_automatic_baseline_calibration",
        translation_key="co2_automatic_baseline_calibration",
        options=ABC_DAYS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: _get_value(
            config.co2_automatic_baseline_calibration_days, ABC_DAYS
        ),
        set_value_fn=lambda client,
        value: client.set_co2_automatic_baseline_calibration(int(value)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirGradientConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirGradient select entities based on a config entry."""

    coordinator = entry.runtime_data
    model = coordinator.data.measures.model

    async_add_entities([AirGradientSelect(coordinator, CONFIG_CONTROL_ENTITY)])

    added_entities = False

    @callback
    def _async_check_entities() -> None:
        nonlocal added_entities

        if (
            coordinator.data.config.configuration_control is ConfigurationControl.LOCAL
            and not added_entities
        ):
            entities: list[AirGradientSelect] = [
                AirGradientSelect(coordinator, description)
                for description in CONTROL_ENTITIES
            ]
            if "I" in model:
                entities.extend(
                    AirGradientSelect(coordinator, description)
                    for description in DISPLAY_SELECT_TYPES
                )
            if "L" in model:
                entities.extend(
                    AirGradientSelect(coordinator, description)
                    for description in LED_BAR_ENTITIES
                )

            async_add_entities(entities)
            added_entities = True
        elif (
            coordinator.data.config.configuration_control
            is not ConfigurationControl.LOCAL
            and added_entities
        ):
            entity_registry = er.async_get(hass)
            for entity_description in (
                DISPLAY_SELECT_TYPES + LED_BAR_ENTITIES + CONTROL_ENTITIES
            ):
                unique_id = f"{coordinator.serial_number}-{entity_description.key}"
                if entity_id := entity_registry.async_get_entity_id(
                    SELECT_DOMAIN, DOMAIN, unique_id
                ):
                    entity_registry.async_remove(entity_id)
            added_entities = False

    coordinator.async_add_listener(_async_check_entities)
    _async_check_entities()


class AirGradientSelect(AirGradientEntity, SelectEntity):
    """Defines an AirGradient select entity."""

    entity_description: AirGradientSelectEntityDescription

    def __init__(
        self,
        coordinator: AirGradientCoordinator,
        description: AirGradientSelectEntityDescription,
    ) -> None:
        """Initialize AirGradient select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the state of the select."""
        return self.entity_description.value_fn(self.coordinator.data.config)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(self.coordinator.client, option)
        await self.coordinator.async_request_refresh()

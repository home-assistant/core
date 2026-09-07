"""Support for AirGradient select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from airgradient import AirGradientClient, Config, GpsMode
from airgradient.models import ConfigurationControl, LedBarMode, TemperatureUnit

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirGradientConfigEntry
from .const import DOMAIN, PM_STANDARD, PM_STANDARD_REVERSE, supports_config
from .coordinator import AirGradientCoordinator
from .entity import AirGradientEntity, exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AirGradientSelectEntityDescription(SelectEntityDescription):
    """Describes AirGradient select entity."""

    config_key: str
    value_fn: Callable[[Config], str | None]
    set_value_fn: Callable[[AirGradientClient, str], Awaitable[None]]


CONFIG_CONTROL_ENTITY = AirGradientSelectEntityDescription(
    key="configuration_control",
    translation_key="configuration_control",
    options=[ConfigurationControl.CLOUD.value, ConfigurationControl.LOCAL.value],
    entity_category=EntityCategory.CONFIG,
    config_key="configuration_control",
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
        config_key="temperature_unit",
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
        config_key="pm_standard",
        value_fn=lambda config: (
            PM_STANDARD.get(config.pm_standard) if config.pm_standard else None
        ),
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
        config_key="led_bar_mode",
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
    "7",
    "8",
    "30",
    "90",
    "180",
    "0",
]


def _get_value(value: int | None, values: list[str]) -> str | None:
    str_value = str(value)
    return str_value if str_value in values else None


def _get_led_level(value: int | None, options: list[str]) -> str | None:
    """Return a semantic LED-level option."""
    return options[value] if value is not None and 0 <= value < len(options) else None


LED_BRIGHTNESS_OPTIONS = ["off", "dim", "mid", "bright"]
TOUCH_LED_INTENSITY_OPTIONS = ["off", "dim", "bright"]


CONTROL_ENTITIES: tuple[AirGradientSelectEntityDescription, ...] = (
    AirGradientSelectEntityDescription(
        key="nox_index_learning_time_offset",
        translation_key="nox_index_learning_time_offset",
        options=LEARNING_TIME_OFFSET_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        config_key="nox_learning_offset",
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
        config_key="tvoc_learning_offset",
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
        config_key="co2_automatic_baseline_calibration_days",
        value_fn=lambda config: _get_value(
            config.co2_automatic_baseline_calibration_days, ABC_DAYS
        ),
        set_value_fn=lambda client, value: (
            client.set_co2_automatic_baseline_calibration(int(value))
        ),
    ),
)

GO_SELECT_ENTITIES: tuple[AirGradientSelectEntityDescription, ...] = (
    AirGradientSelectEntityDescription(
        key="gps_mode",
        translation_key="gps_mode",
        options=[mode.value for mode in GpsMode],
        entity_category=EntityCategory.CONFIG,
        config_key="gps_mode",
        value_fn=lambda config: config.gps_mode,
        set_value_fn=lambda client, value: client.set_gps_mode(GpsMode(value)),
    ),
    AirGradientSelectEntityDescription(
        key="front_led_brightness",
        translation_key="front_led_brightness",
        options=LED_BRIGHTNESS_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        config_key="front_led_brightness",
        value_fn=lambda config: _get_led_level(
            config.front_led_brightness, LED_BRIGHTNESS_OPTIONS
        ),
        set_value_fn=lambda client, value: client.set_front_led_brightness(
            LED_BRIGHTNESS_OPTIONS.index(value)
        ),
    ),
    AirGradientSelectEntityDescription(
        key="back_led_brightness",
        translation_key="back_led_brightness",
        options=LED_BRIGHTNESS_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        config_key="back_led_brightness",
        value_fn=lambda config: _get_led_level(
            config.back_led_brightness, LED_BRIGHTNESS_OPTIONS
        ),
        set_value_fn=lambda client, value: client.set_back_led_brightness(
            LED_BRIGHTNESS_OPTIONS.index(value)
        ),
    ),
    AirGradientSelectEntityDescription(
        key="touch_led_intensity",
        translation_key="touch_led_intensity",
        options=TOUCH_LED_INTENSITY_OPTIONS,
        entity_category=EntityCategory.CONFIG,
        config_key="touch_led_intensity",
        value_fn=lambda config: _get_led_level(
            config.touch_led_intensity, TOUCH_LED_INTENSITY_OPTIONS
        ),
        set_value_fn=lambda client, value: client.set_touch_led_intensity(
            TOUCH_LED_INTENSITY_OPTIONS.index(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirGradientConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirGradient select entities based on a config entry."""

    coordinator = entry.runtime_data
    model = coordinator.data.measures.model
    descriptions = (
        CONFIG_CONTROL_ENTITY,
        *DISPLAY_SELECT_TYPES,
        *LED_BAR_ENTITIES,
        *CONTROL_ENTITIES,
        *GO_SELECT_ENTITIES,
    )
    descriptions_by_key = {description.key: description for description in descriptions}
    added_entities: set[str] = set()

    @callback
    def _async_check_entities() -> None:
        nonlocal added_entities
        config = coordinator.data.config
        desired_entities = {
            description.key
            for description in descriptions
            if supports_config(
                model, coordinator.client.api_version, config, description.config_key
            )
            and (
                description is CONFIG_CONTROL_ENTITY
                or config.configuration_control is ConfigurationControl.LOCAL
            )
        }

        if entities_to_add := desired_entities - added_entities:
            async_add_entities(
                [
                    AirGradientSelect(coordinator, descriptions_by_key[key])
                    for key in entities_to_add
                ]
            )
        if entities_to_remove := added_entities - desired_entities:
            entity_registry = er.async_get(hass)
            for key in entities_to_remove:
                unique_id = f"{coordinator.serial_number}-{key}"
                if entity_id := entity_registry.async_get_entity_id(
                    SELECT_DOMAIN, DOMAIN, unique_id
                ):
                    entity_registry.async_remove(entity_id)
        added_entities = desired_entities

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
    @override
    def current_option(self) -> str | None:
        """Return the state of the select."""
        return self.entity_description.value_fn(self.coordinator.data.config)

    @exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(self.coordinator.client, option)
        await self.coordinator.async_request_refresh()

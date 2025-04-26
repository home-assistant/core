"""Number platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

from pylamarzocco import LaMarzoccoMachine
from pylamarzocco.const import ModelName, PreExtractionMode, WidgetType
from pylamarzocco.exceptions import RequestNotSuccessful
from pylamarzocco.models import CoffeeBoiler, PreBrewing

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoNumberEntityDescription(
    LaMarzoccoEntityDescription,
    NumberEntityDescription,
):
    """Description of a La Marzocco number entity."""

    native_value_fn: Callable[[LaMarzoccoMachine], float | int]
    set_value_fn: Callable[[LaMarzoccoMachine, float | int], Coroutine[Any, Any, bool]]


ENTITIES: tuple[LaMarzoccoNumberEntityDescription, ...] = (
    LaMarzoccoNumberEntityDescription(
        key="coffee_temp",
        translation_key="coffee_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_step=PRECISION_TENTHS,
        native_min_value=85,
        native_max_value=104,
        set_value_fn=lambda machine, temp: machine.set_coffee_target_temperature(temp),
        native_value_fn=(
            lambda machine: cast(
                CoffeeBoiler, machine.dashboard.config[WidgetType.CM_COFFEE_BOILER]
            ).target_temperature
        ),
    ),
    LaMarzoccoNumberEntityDescription(
        key="smart_standby_time",
        translation_key="smart_standby_time",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_step=PRECISION_WHOLE,
        native_min_value=0,
        native_max_value=240,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=(
            lambda machine, value: machine.set_smart_standby(
                enabled=machine.schedule.smart_wake_up_sleep.smart_stand_by_enabled,
                mode=machine.schedule.smart_wake_up_sleep.smart_stand_by_after,
                minutes=int(value),
            )
        ),
        native_value_fn=lambda machine: machine.schedule.smart_wake_up_sleep.smart_stand_by_minutes,
    ),
    LaMarzoccoNumberEntityDescription(
        key="preinfusion_off",
        translation_key="preinfusion_time",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_step=PRECISION_TENTHS,
        native_min_value=0,
        native_max_value=10,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=(
            lambda machine, value: machine.set_pre_extraction_times(
                seconds_on=0,
                seconds_off=float(value),
            )
        ),
        native_value_fn=(
            lambda machine: cast(
                PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]
            )
            .times.pre_infusion[0]
            .seconds.seconds_out
        ),
        available_fn=(
            lambda machine: cast(
                PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]
            ).mode
            is PreExtractionMode.PREINFUSION
        ),
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            in (
                ModelName.LINEA_MICRA,
                ModelName.LINEA_MINI,
                ModelName.LINEA_MINI_R,
            )
        ),
    ),
    LaMarzoccoNumberEntityDescription(
        key="prebrew_on",
        translation_key="prebrew_time_on",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_step=PRECISION_TENTHS,
        native_min_value=0,
        native_max_value=10,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=(
            lambda machine, value: machine.set_pre_extraction_times(
                seconds_on=float(value),
                seconds_off=cast(
                    PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]
                )
                .times.pre_brewing[0]
                .seconds.seconds_out,
            )
        ),
        native_value_fn=(
            lambda machine: cast(
                PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]
            )
            .times.pre_brewing[0]
            .seconds.seconds_in
        ),
        available_fn=lambda machine: cast(
            PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]
        ).mode
        is PreExtractionMode.PREBREWING,
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            in (
                ModelName.LINEA_MICRA,
                ModelName.LINEA_MINI,
                ModelName.LINEA_MINI_R,
            )
        ),
    ),
    LaMarzoccoNumberEntityDescription(
        key="prebrew_off",
        translation_key="prebrew_time_off",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_step=PRECISION_TENTHS,
        native_min_value=0,
        native_max_value=10,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=(
            lambda machine, value: machine.set_pre_extraction_times(
                seconds_on=cast(
                    PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]
                )
                .times.pre_brewing[0]
                .seconds.seconds_in,
                seconds_off=float(value),
            )
        ),
        native_value_fn=(
            lambda machine: cast(
                PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]
            )
            .times.pre_brewing[0]
            .seconds.seconds_out
        ),
        available_fn=(
            lambda machine: cast(
                PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]
            ).mode
            is PreExtractionMode.PREBREWING
        ),
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            in (
                ModelName.LINEA_MICRA,
                ModelName.LINEA_MINI,
                ModelName.LINEA_MINI_R,
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data.config_coordinator
    entities: list[NumberEntity] = [
        LaMarzoccoNumberEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    ]

    async_add_entities(entities)


class LaMarzoccoNumberEntity(LaMarzoccoEntity, NumberEntity):
    """La Marzocco number entity."""

    entity_description: LaMarzoccoNumberEntityDescription

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_description.native_value_fn(self.coordinator.device)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        if value != self.native_value:
            try:
                await self.entity_description.set_value_fn(
                    self.coordinator.device, value
                )
            except RequestNotSuccessful as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="number_exception",
                    translation_placeholders={
                        "key": self.entity_description.key,
                        "value": str(value),
                    },
                ) from exc
            self.async_write_ha_state()

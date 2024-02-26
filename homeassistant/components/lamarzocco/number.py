"""Number platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lmcloud import LMCloud as LaMarzoccoClient
from lmcloud.const import LaMarzoccoModel

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoUpdateCoordinator
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoNumberEntityDescription(
    LaMarzoccoEntityDescription,
    NumberEntityDescription,
):
    """Description of a La Marzocco number entity."""

    native_value_fn: Callable[[LaMarzoccoClient], float | int]
    set_value_fn: Callable[
        [LaMarzoccoUpdateCoordinator, float | int], Coroutine[Any, Any, bool]
    ]


ENTITIES: tuple[LaMarzoccoNumberEntityDescription, ...] = (
    LaMarzoccoNumberEntityDescription(
        key="coffee_temp",
        translation_key="coffee_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_step=PRECISION_TENTHS,
        native_min_value=85,
        native_max_value=104,
        set_value_fn=lambda coordinator, temp: coordinator.lm.set_coffee_temp(temp),
        native_value_fn=lambda lm: lm.current_status["coffee_set_temp"],
    ),
    LaMarzoccoNumberEntityDescription(
        key="steam_temp",
        translation_key="steam_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_step=PRECISION_WHOLE,
        native_min_value=126,
        native_max_value=131,
        set_value_fn=lambda coordinator, temp: coordinator.lm.set_steam_temp(int(temp)),
        native_value_fn=lambda lm: lm.current_status["steam_set_temp"],
        supported_fn=lambda coordinator: coordinator.lm.model_name
        in (
            LaMarzoccoModel.GS3_AV,
            LaMarzoccoModel.GS3_MP,
        ),
    ),
    LaMarzoccoNumberEntityDescription(
        key="tea_water_duration",
        translation_key="tea_water_duration",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_step=PRECISION_WHOLE,
        native_min_value=0,
        native_max_value=30,
        set_value_fn=lambda coordinator, value: coordinator.lm.set_dose_hot_water(
            value=int(value)
        ),
        native_value_fn=lambda lm: lm.current_status["dose_hot_water"],
        supported_fn=lambda coordinator: coordinator.lm.model_name
        in (
            LaMarzoccoModel.GS3_AV,
            LaMarzoccoModel.GS3_MP,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LaMarzoccoNumberEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoNumberEntity(LaMarzoccoEntity, NumberEntity):
    """La Marzocco number entity."""

    entity_description: LaMarzoccoNumberEntityDescription

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_description.native_value_fn(self.coordinator.lm)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.entity_description.set_value_fn(self.coordinator, value)
        self.async_write_ha_state()

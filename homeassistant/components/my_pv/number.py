# pylint: disable=duplicate-code
"""Creates Number entities for the my-PV Home Assistant integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, override

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyPVConfigEntry
from .const import DOMAIN
from .entity import MyPVSetupEntity

type MyPVConfig = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class MyPVNumberEntityDescription(NumberEntityDescription):
    """my-PV number entity description."""

    native_unit_of_measurement_fn: Callable[[MyPVConfig], str | None] = lambda config: (
        config.get("unit")
    )
    native_min_value_fn: Callable[[MyPVConfig], float] = lambda config: float(
        config.get("min", DEFAULT_MIN_VALUE)
    )
    native_max_value_fn: Callable[[MyPVConfig], float] = lambda config: float(
        config.get("max", DEFAULT_MAX_VALUE)
    )
    native_step_fn: Callable[[MyPVConfig], float | None] = lambda config: (
        float(step) if (step := config.get("step")) is not None else None
    )


ENTITY_DESCRIPTIONS: Final[dict[str, MyPVNumberEntityDescription]] = {
    "bsttemp": MyPVNumberEntityDescription(
        key="bsttemp",
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="ww1boost",
    ),
    "ww1boost": MyPVNumberEntityDescription(
        key="ww1boost",
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="ww1boost",
    ),
    "ww_boost_h": MyPVNumberEntityDescription(
        key="ww_boost_h",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        translation_key="ww_boost_h",
    ),
    "ww_targ_h": MyPVNumberEntityDescription(
        key="ww_targ_h",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        translation_key="ww_targ_h",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV number."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MyPVNumber(
            coordinator,
            ENTITY_DESCRIPTIONS[key],
            coordinator.device.serial_number,
        )
        for key, config in coordinator.device.get_setup_configurations().items()
        if config.get("type") == "number" and key in ENTITY_DESCRIPTIONS
    )


class MyPVNumber(MyPVSetupEntity, NumberEntity):
    """my-PV number."""

    entity_description: MyPVNumberEntityDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        value = self.coordinator.device.get_setup_value(self.entity_description.key)
        return float(value) if value is not None else None

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the entity, if any."""
        return self.entity_description.native_unit_of_measurement_fn(
            self._configuration
        )

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.entity_description.native_min_value_fn(self._configuration)

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.entity_description.native_max_value_fn(self._configuration)

    @property
    @override
    def native_step(self) -> float | None:
        """Return the increment/decrement step."""
        return self.entity_description.native_step_fn(self._configuration)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if not await self.coordinator.set_setup_value(
            self.entity_description.key, value
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

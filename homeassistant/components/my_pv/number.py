"""Creates Number entities for the my-PV integration."""

from typing import Any, Final, override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MyPVConfigEntry, MyPVCoordinator
from .entity import MyPVSetupEntity

PARALLEL_UPDATES = 0

ENTITY_DESCRIPTIONS: Final[tuple[NumberEntityDescription, ...]] = (
    NumberEntityDescription(
        key="bsttemp",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        translation_key="ww1boost",
    ),
    NumberEntityDescription(
        key="ww1boost",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        translation_key="ww1boost",
    ),
    NumberEntityDescription(
        key="ww_boost_h",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        translation_key="ww_boost_h",
    ),
    NumberEntityDescription(
        key="ww_targ_h",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        translation_key="ww_targ_h",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV number."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MyPVNumber(coordinator, entity_description, config)
        for entity_description in ENTITY_DESCRIPTIONS
        if (
            config := coordinator.device.get_setup_configuration(entity_description.key)
        )
        and config.get("type") == "number"
    )


class MyPVNumber(MyPVSetupEntity, NumberEntity):
    """my-PV number."""

    entity_description: NumberEntityDescription

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: NumberEntityDescription,
        config: dict[str, Any],
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, entity_description)

        self._attr_native_unit_of_measurement = config.get("unit")
        self._attr_native_min_value = config.get("min", 0)
        if (max_value := config.get("max")) is not None:
            self._attr_native_max_value = max_value
        if (step := config.get("step")) is not None:
            self._attr_native_step = step

    @property
    @override
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        value = self.coordinator.device.get_setup_value(self.entity_description.key)
        return float(value) if value is not None else None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if not await self.coordinator.set_setup_value(
            self.entity_description.key, value
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

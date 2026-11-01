# pylint: disable=duplicate-code
"""Creates Number entities for the my-PV Home Assistant integration."""

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

from . import MyPVConfigEntry
from .const import DOMAIN
from .entity import MyPVSetupEntity

NUMBER_DESCRIPTIONS: Final[dict[str, dict[str, Any]]] = {
    "bsttemp": {
        "device_class": NumberDeviceClass.TEMPERATURE,
        "translation_key": "ww1boost",
    },
    "ww1boost": {
        "device_class": NumberDeviceClass.TEMPERATURE,
        "translation_key": "ww1boost",
    },
    "ww_boost_h": {
        "device_class": NumberDeviceClass.TEMPERATURE_DELTA,
        "entity_category": EntityCategory.CONFIG,
        "enabled": False,
        "translation_key": "ww_boost_h",
    },
    "ww_targ_h": {
        "device_class": NumberDeviceClass.TEMPERATURE_DELTA,
        "entity_category": EntityCategory.CONFIG,
        "enabled": False,
        "translation_key": "ww_targ_h",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV number."""
    coordinator = config_entry.runtime_data
    entities = []

    for key, config in coordinator.device.get_setup_configurations().items():
        if config.get("type") == "number" and key in NUMBER_DESCRIPTIONS:
            number_description: dict = NUMBER_DESCRIPTIONS[key]
            entity_description = NumberEntityDescription(
                key=key,
                device_class=number_description.get("device_class"),
                entity_category=number_description.get("entity_category"),
                translation_key=number_description.get("translation_key"),
                native_unit_of_measurement=config.get("unit"),
                native_min_value=config.get("min", 0),
                native_max_value=config.get("max"),
                native_step=config.get("step"),
                entity_registry_enabled_default=number_description.get("enabled", True),
            )
            entities.append(
                MyPVNumber(
                    coordinator,
                    entity_description,
                    coordinator.device.serial_number,
                )
            )

    async_add_entities(entities)


class MyPVNumber(MyPVSetupEntity, NumberEntity):
    """my-PV number."""

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

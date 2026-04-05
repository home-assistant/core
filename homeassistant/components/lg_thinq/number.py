"""Support for number entities."""

from __future__ import annotations

import logging

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode, TimerProperty

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from . import ThinqConfigEntry
from .const import DOMAIN
from .entity import ThinQEntity

NUMBER_DESC: dict[ThinQProperty, NumberEntityDescription] = {
    ThinQProperty.FAN_SPEED: NumberEntityDescription(
        key=ThinQProperty.FAN_SPEED,
        translation_key=ThinQProperty.FAN_SPEED,
        entity_registry_enabled_default=False,
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
    DeviceType.WATER_HEATER: (NUMBER_DESC[ThinQProperty.TARGET_TEMPERATURE],),
    DeviceType.WINE_CELLAR: (
        NUMBER_DESC[ThinQProperty.LIGHT_STATUS],
        NUMBER_DESC[ThinQProperty.TARGET_TEMPERATURE],
    ),
    DeviceType.VENTILATOR: (
        TIMER_NUMBER_DESC[ThinQProperty.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP],
    ),
}

DEPRECATED_FAN_SPEED_DEVICE_TYPES: set[DeviceType] = {
    DeviceType.HOOD,
    DeviceType.MICROWAVE_OVEN,
}

_LOGGER = logging.getLogger(__name__)


def _check_deprecated_fan_speed_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    unique_id: str,
) -> bool:
    """Check if a deprecated fan speed number entity should be created.

    Returns True if the entity exists and is enabled (should still be created).
    """
    if not (
        entity_id := entity_registry.async_get_entity_id("number", DOMAIN, unique_id)
    ):
        return False

    entity_entry = entity_registry.async_get(entity_id)
    if not entity_entry:
        return False

    if entity_entry.disabled:
        entity_registry.async_remove(entity_id)
        async_delete_issue(hass, DOMAIN, f"deprecated_fan_speed_number_{entity_id}")
        return False

    translation_key = "deprecated_fan_speed_number"
    placeholders: dict[str, str] = {
        "entity_id": entity_id,
        "entity_name": entity_entry.name or entity_entry.original_name or "Unknown",
    }

    automation_entities = automations_with_entity(hass, entity_id)
    script_entities = scripts_with_entity(hass, entity_id)
    if automation_entities or script_entities:
        translation_key = f"{translation_key}_scripts"
        placeholders["items"] = "\n".join(
            f"- [{item.original_name}](/config/{integration}/edit/{item.unique_id})"
            for integration, entities in (
                ("automation", automation_entities),
                ("script", script_entities),
            )
            for eid in entities
            if (item := entity_registry.async_get(eid))
        )

    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_fan_speed_number_{entity_id}",
        breaks_in_ha_version="2026.11.0",
        is_fixable=True,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders,
        data={"entity_id": entity_id, **placeholders},
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for number platform."""
    entities: list[ThinQNumberEntity] = []
    entity_registry = er.async_get(hass)
    for coordinator in entry.runtime_data.coordinators.values():
        descriptions = DEVICE_TYPE_NUMBER_MAP.get(coordinator.api.device.device_type)
        if descriptions is None:
            continue
        for description in descriptions:
            for property_id in coordinator.api.get_active_idx(
                description.key, ActiveMode.READ_WRITE
            ):
                if (
                    description.key == ThinQProperty.FAN_SPEED
                    and coordinator.api.device.device_type
                    in DEPRECATED_FAN_SPEED_DEVICE_TYPES
                ):
                    unique_id = f"{coordinator.unique_id}_{property_id}"
                    if not _check_deprecated_fan_speed_entity(
                        hass, entity_registry, unique_id
                    ):
                        continue
                entities.append(
                    ThinQNumberEntity(coordinator, description, property_id)
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

        # Update range.
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

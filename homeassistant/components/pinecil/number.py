"""Number platform for Pinecil integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pinecil.pinecil_setting_limits import MAX_TEMP_C, MIN_BOOST_TEMP_C, MIN_TEMP_C

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PinecilConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL, PinecilEntity
from .coordinator import PinecilCoordinator


@dataclass(frozen=True, kw_only=True)
class PinecilNumberEntityDescription(NumberEntityDescription):
    """Describes Pinecil sensor entity."""

    value_fn: Callable[[dict, dict], float | int | None]
    set_fn: Callable[[int | float], float | int] | None = None
    max_value_fn: Callable[[Any], float]
    set_key: str


SENSOR_DESCRIPTIONS: tuple[PinecilNumberEntityDescription, ...] = (
    PinecilNumberEntityDescription(
        key=PinecilEntity.SETPOINT_TEMP,
        translation_key=PinecilEntity.SETPOINT_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_fn=lambda data, settings: data.get("SetTemp"),
        set_key="SetTemperature",
        mode=NumberMode.BOX,
        native_min_value=MIN_TEMP_C,
        native_step=5,
        max_value_fn=lambda data: min(
            data.get("MaxTipTempAbility", MAX_TEMP_C), MAX_TEMP_C
        ),
    ),
    PinecilNumberEntityDescription(
        key=PinecilEntity.SLEEP_TEMP,
        translation_key=PinecilEntity.SLEEP_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_fn=lambda data, settings: settings.get("SleepTemperature"),
        set_key="SleepTemperature",
        mode=NumberMode.BOX,
        native_min_value=MIN_TEMP_C,
        native_step=10,
        max_value_fn=lambda data: MAX_TEMP_C,
        entity_category=EntityCategory.CONFIG,
    ),
    PinecilNumberEntityDescription(
        key=PinecilEntity.BOOST_TEMP,
        translation_key=PinecilEntity.BOOST_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        value_fn=lambda data, settings: settings.get("BoostTemperature"),
        set_key="BoostTemperature",
        mode=NumberMode.BOX,
        native_min_value=MIN_BOOST_TEMP_C,
        native_step=10,
        max_value_fn=lambda data: MAX_TEMP_C,
        entity_category=EntityCategory.CONFIG,
    ),
    PinecilNumberEntityDescription(
        key=PinecilEntity.QC_MAX_VOLTAGE,
        translation_key=PinecilEntity.QC_MAX_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        value_fn=lambda data, settings: float(settings.get("QCMaxVoltage", 9.0) / 10),
        set_fn=lambda value: value * 10,
        set_key="QCMaxVoltage",
        mode=NumberMode.BOX,
        native_min_value=9.0,
        native_step=0.1,
        max_value_fn=lambda _: 22.0,
        entity_category=EntityCategory.CONFIG,
    ),
    PinecilNumberEntityDescription(
        key=PinecilEntity.PD_TIMEOUT,
        translation_key=PinecilEntity.PD_TIMEOUT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        value_fn=lambda data, settings: settings.get("PDNegTimeout", 0) / 10,
        set_key="PDNegTimeout",
        set_fn=lambda value: value * 10,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_step=1,
        max_value_fn=lambda _: 5.0,
        entity_category=EntityCategory.CONFIG,
    ),
    PinecilNumberEntityDescription(
        key=PinecilEntity.SHUTDOWN_TIMEOUT,
        translation_key=PinecilEntity.SHUTDOWN_TIMEOUT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=NumberDeviceClass.DURATION,
        value_fn=lambda data, settings: settings.get("ShutdownTimeout", 0),
        set_key="ShutdownTimeout",
        mode=NumberMode.BOX,
        native_min_value=0,
        native_step=1,
        max_value_fn=lambda _: 60,
        entity_category=EntityCategory.CONFIG,
    ),
    PinecilNumberEntityDescription(
        key=PinecilEntity.DISPLAY_BRIGHTNESS,
        translation_key=PinecilEntity.DISPLAY_BRIGHTNESS,
        value_fn=lambda data, settings: int(settings.get("Brightness", 10) / 25 + 1),
        set_fn=lambda value: (value - 1) * 25,
        set_key="Brightness",
        mode=NumberMode.SLIDER,
        native_min_value=1,
        native_step=1,
        max_value_fn=lambda _: 5,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PinecilConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        PinecilNumber(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class PinecilNumber(CoordinatorEntity[PinecilCoordinator], NumberEntity):
    """Implementation of a Pinecil sensor."""

    _attr_has_entity_name = True
    entity_description: PinecilNumberEntityDescription

    def __init__(
        self,
        coordinator: PinecilCoordinator,
        entity_description: PinecilNumberEntityDescription,
        entry: PinecilConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        assert entry.unique_id
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.unique_id}_{entity_description.key}"
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            connections={(CONNECTION_BLUETOOTH, entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name="Pinecil",
            sw_version=coordinator.device.get("build"),
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""

        if self.entity_description.set_fn:
            value = self.entity_description.set_fn(value)
        await self.coordinator.pinecil.set_one_setting(
            self.entity_description.set_key, int(value)
        )

    @property
    def native_value(self) -> float | int | None:
        """Return sensor state."""
        return self.entity_description.value_fn(
            self.coordinator.data, self.coordinator.settings
        )

    @property
    def native_max_value(self) -> float:
        """Return sensor state."""
        return self.entity_description.max_value_fn(self.coordinator.data)

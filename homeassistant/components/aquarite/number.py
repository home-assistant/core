"""Aquarite Number entities."""
from __future__ import annotations

from typing import Final

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import EntityCategory, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .const import DOMAIN
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aquarite number entities."""
    dataservice = entry.runtime_data
    pool_id, pool_name = dataservice.pool_id, entry.title

    # Safely determine max electrolysis
    raw_max = dataservice.get_value("hidro.maxAllowedValue", 0)
    try:
        max_electrolysis = int(raw_max) / 10 if raw_max else 50.0
    except (ValueError, TypeError):
        max_electrolysis = 50.0

    entities = [
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            500, 800, "redox_setpoint", "modules.rx.status.value",
        ),
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            6, 8, "ph_low", "modules.ph.status.low_value",
        ),
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            6, 8, "ph_max", "modules.ph.status.high_value",
        ),
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            0, max_electrolysis, "electrolysis_setpoint", "hidro.level",
        ),
        # INTEL mode target temperature (matches the "Température" field shown
        # under the INTEL slider position in the Hayward app).
        AquariteNumberEntity(
            dataservice, pool_id, pool_name,
            5, 40, "intel_mode_temperature", "filtration.intel.temp",
        ),
    ]

    # HEAT mode min/max range.
    if dataservice.get_value("filtration.hasHeat"):
        entities.extend([
            AquariteNumberEntity(
                dataservice, pool_id, pool_name,
                5, 40, "heating_mode_min_temperature", "filtration.heating.temp",
            ),
            AquariteNumberEntity(
                dataservice, pool_id, pool_name,
                5, 40, "heating_mode_max_temperature", "filtration.heating.tempHi",
            ),
        ])

    # SMART mode min/max range.
    if dataservice.get_value("filtration.hasSmart"):
        entities.extend([
            AquariteNumberEntity(
                dataservice, pool_id, pool_name,
                5, 40, "smart_mode_min_temperature", "filtration.smart.tempMin",
            ),
            AquariteNumberEntity(
                dataservice, pool_id, pool_name,
                5, 40, "smart_mode_max_temperature", "filtration.smart.tempHigh",
            ),
        ])

    async_add_entities(entities)


class AquariteNumberEntity(AquariteEntity, NumberEntity):
    """Number entity for Aquarite data points."""

    _attr_entity_category = EntityCategory.CONFIG

    SCALE_MAP: Final[dict[str, int]] = {
        "modules.ph.status.low_value": 100,
        "modules.ph.status.high_value": 100,
        "hidro.level": 10,
    }
    UNIT_MAP: Final[dict[str, str]] = {
        "modules.rx.status.value": UnitOfElectricPotential.MILLIVOLT,
        "modules.ph.status.low_value": "pH",
        "modules.ph.status.high_value": "pH",
        "hidro.level": "gr/h",
        "filtration.heating.temp": UnitOfTemperature.CELSIUS,
        "filtration.heating.tempHi": UnitOfTemperature.CELSIUS,
        "filtration.intel.temp": UnitOfTemperature.CELSIUS,
        "filtration.smart.tempMin": UnitOfTemperature.CELSIUS,
        "filtration.smart.tempHigh": UnitOfTemperature.CELSIUS,
    }
    DEVICE_CLASS_MAP: Final[dict[str, NumberDeviceClass]] = {
        "filtration.heating.temp": NumberDeviceClass.TEMPERATURE,
        "filtration.heating.tempHi": NumberDeviceClass.TEMPERATURE,
        "filtration.intel.temp": NumberDeviceClass.TEMPERATURE,
        "filtration.smart.tempMin": NumberDeviceClass.TEMPERATURE,
        "filtration.smart.tempHigh": NumberDeviceClass.TEMPERATURE,
    }

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        value_min: float,
        value_max: float,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._attr_native_min_value = value_min
        self._attr_native_max_value = value_max
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)
        self._attr_native_unit_of_measurement = self.UNIT_MAP.get(value_path)
        self._attr_device_class = self.DEVICE_CLASS_MAP.get(value_path)
        self._attr_native_step = self._get_scaled_step()

    def _get_scaled_step(self) -> float:
        """Return step size based on scale factor."""
        scale = self.SCALE_MAP.get(self._value_path)
        return 1 / scale if scale else 1.0

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        raw_value = self.coordinator.get_value(self._value_path)
        if raw_value is None:
            return None
        scale = self.SCALE_MAP.get(self._value_path)
        try:
            return int(raw_value) / scale if scale else float(raw_value)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        scale = self.SCALE_MAP.get(self._value_path)
        raw_value = int(round(value * scale)) if scale else value
        try:
            await self.coordinator.api.set_value(
                self._pool_id, self._value_path, raw_value
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

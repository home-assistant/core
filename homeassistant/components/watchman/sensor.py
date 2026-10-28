"""Sensor platform for Kingspan Watchman SENSiT."""

# pylint: disable=unexpected-keyword-arg

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import logging
from typing import override

from connectsensor.analysis import TankData

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_OIL_ENERGY_DENSITY, DEFAULT_OIL_ENERGY_DENSITY
from .coordinator import SENSiTConfigEntry, SENSiTDataUpdateCoordinator
from .entity import SENSiTEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)

PARALLEL_UPDATES = 0


def _get_energy_density(config_entry: SENSiTConfigEntry) -> float:
    """Return configured oil energy density."""
    return float(
        config_entry.options.get(
            CONF_OIL_ENERGY_DENSITY,
            config_entry.data.get(
                CONF_OIL_ENERGY_DENSITY,
                DEFAULT_OIL_ENERGY_DENSITY,
            ),
        )
    )


@dataclass(frozen=True, kw_only=True)
class SENSiTSensorEntityDescription(SensorEntityDescription):
    """Describes a Kingspan Watchman SENSiT sensor entity."""

    value_fn: Callable[
        [TankData, SENSiTConfigEntry], float | int | Decimal | datetime | None
    ]


SENSOR_DESCRIPTIONS: tuple[SENSiTSensorEntityDescription, ...] = (
    SENSiTSensorEntityDescription(
        key="oil_level",
        translation_key="oil_level",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda tank, _: tank.level,
    ),
    SENSiTSensorEntityDescription(
        key="tank_percentage_full",
        translation_key="tank_percentage_full",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda tank, _: (
            Decimal(f"{100 * (tank.level / tank.capacity):.1f}")
            if tank.capacity > 0
            else Decimal("0.0")
        ),
    ),
    SENSiTSensorEntityDescription(
        key="tank_capacity",
        translation_key="tank_capacity",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda tank, _: tank.capacity,
    ),
    SENSiTSensorEntityDescription(
        key="last_reading_date",
        translation_key="last_reading_date",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda tank, _: tank.last_read,
    ),
    SENSiTSensorEntityDescription(
        key="current_usage",
        translation_key="current_usage",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=lambda tank, _: Decimal(f"{tank.usage_rate:.1f}"),
    ),
    SENSiTSensorEntityDescription(
        key="forecast_empty",
        translation_key="forecast_empty",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda tank, _: tank.forecast_empty,
    ),
    SENSiTSensorEntityDescription(
        key="current_energy_usage",
        translation_key="current_energy_usage",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda tank, entry: round(
            float(tank.usage_rate * _get_energy_density(entry)), 1
        ),
    ),
)

OIL_CONSUMPTION_DESCRIPTION = SensorEntityDescription(
    key="oil_consumption",
    translation_key="oil_consumption",
    entity_registry_enabled_default=False,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    state_class=SensorStateClass.TOTAL_INCREASING,
    device_class=SensorDeviceClass.ENERGY,
    suggested_display_precision=1,
)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: SENSiTConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform and listen for new dynamically added tanks."""
    coordinator = config_entry.runtime_data
    added_tanks: set[str] = set()

    @callback
    def async_add_new_tanks() -> None:
        new_entities: list[SENSiTEntity] = []
        for tank in coordinator.data:
            if tank.serial_number not in added_tanks:
                added_tanks.add(tank.serial_number)
                new_entities.extend(
                    SENSiTSensor(
                        coordinator, config_entry, tank.serial_number, description
                    )
                    for description in SENSOR_DESCRIPTIONS
                )
                new_entities.append(
                    OilConsumptionSensor(
                        coordinator,
                        config_entry,
                        tank.serial_number,
                        OIL_CONSUMPTION_DESCRIPTION,
                    )
                )
        if new_entities:
            async_add_entities(new_entities)

    async_add_new_tanks()
    config_entry.async_on_unload(coordinator.async_add_listener(async_add_new_tanks))


class SENSiTSensor(SENSiTEntity, SensorEntity):
    """Representation of a Kingspan Watchman SENSiT sensor."""

    entity_description: SENSiTSensorEntityDescription

    @property
    @override
    def native_value(self) -> float | int | Decimal | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.tank_data, self.config_entry)


class OilConsumptionSensor(SENSiTEntity, RestoreSensor):
    """Sensor that tracks cumulative energy consumption."""

    def __init__(
        self,
        coordinator: SENSiTDataUpdateCoordinator,
        config_entry: SENSiTConfigEntry,
        serial_number: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the cumulative oil consumption sensor."""
        super().__init__(coordinator, config_entry, serial_number, entity_description)
        self._consumption_total: float | None = None
        self._consumption_last_read: datetime | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Restore previous cumulative consumption state."""
        await super().async_added_to_hass()
        if (old_state := await self.async_get_last_state()) is not None:
            raw_last_read = old_state.attributes.get("consumption_last_read")
            if raw_last_read is not None:
                self._consumption_last_read = dt_util.parse_datetime(str(raw_last_read))
            raw_total = old_state.attributes.get("consumption_total")
            if raw_total is not None:
                self._consumption_total = round(float(raw_total), 1)
            _LOGGER.debug(
                "Restoring consumption: %s kWh at %s",
                self._consumption_total,
                self._consumption_last_read,
            )
        self._update_consumption()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_consumption()
        super()._handle_coordinator_update()

    def _update_consumption(self) -> None:
        """Calculate and update cumulative energy consumption when a new reading arrives."""
        last_read = self.tank_data.last_read
        if self._consumption_last_read is None:
            self._consumption_last_read = last_read
            self._consumption_total = 0.0
            return

        if last_read is not None and self._consumption_last_read != last_read:
            usage_rate = self.tank_data.usage_rate
            energy_density = _get_energy_density(self.config_entry)
            base_total = self._consumption_total or 0.0
            self._consumption_total = round(
                base_total + (energy_density * round(usage_rate, 1)), 1
            )
            self._consumption_last_read = last_read

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes for restoration."""
        base_attrs = super().extra_state_attributes or {}
        return {
            **base_attrs,
            "consumption_last_read": self._consumption_last_read,
            "consumption_total": self._consumption_total,
        }

    @property
    @override
    def native_value(self) -> Decimal | None:
        """Return the cumulative energy consumption value."""
        return Decimal(f"{self._consumption_total:.1f}")

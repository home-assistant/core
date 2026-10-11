"""TrueNAS sensor platform."""

from datetime import date, datetime
from decimal import Decimal
from logging import getLogger
from typing import override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utc_from_timestamp

from .const import CONF_DATA_UNIT, DEFAULT_DATA_UNIT
from .coordinator import TrueNASConfigEntry, TrueNASCoordinator, get_truenas_coordinator
from .entity import TrueNASEntity, async_add_entities
from .helper import GB_SCALED_UNITS, scaled_data_unit
from .sensor_types import (  # noqa: F401
    SENSOR_SERVICES,
    SENSOR_TYPES,
    TrueNASSensorEntityDescription,
)

_LOGGER = getLogger(__name__)

# Updates are centralized in the coordinator; entity actions may run unlimited.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TrueNASConfigEntry,
    _async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for TrueNAS component."""
    coordinator: TrueNASCoordinator | None = get_truenas_coordinator(config_entry)
    if coordinator is None:
        return

    dispatcher = {
        "TrueNASSensor": TrueNASSensor,
        "TrueNASUptimeSensor": TrueNASUptimeSensor,
    }
    await async_add_entities(hass, config_entry, dispatcher)


class TrueNASSensor(TrueNASEntity, SensorEntity):
    """Define a TrueNAS sensor."""

    entity_description: TrueNASSensorEntityDescription

    def __init__(
        self,
        coordinator: TrueNASCoordinator,
        entity_description: TrueNASSensorEntityDescription,
        uid: str | None = None,
    ) -> None:
        """Set up the sensor and derive its GB/GiB display unit preference."""
        super().__init__(coordinator, entity_description, uid)
        self._attr_suggested_unit_of_measurement = (
            self.entity_description.suggested_unit_of_measurement
        )

        if self._attr_suggested_unit_of_measurement in GB_SCALED_UNITS:
            data_unit = self.coordinator.config_entry.options.get(
                CONF_DATA_UNIT,
                self.coordinator.config_entry.data.get(
                    CONF_DATA_UNIT, DEFAULT_DATA_UNIT
                ),
            )
            value = (
                self._data.get(self.entity_description.data_attribute or "")
                if self._data
                else None
            )
            unit, precision = scaled_data_unit(value, data_unit == "GiB")
            self._attr_suggested_unit_of_measurement = unit
            if precision is not None:
                self._attr_suggested_display_precision = precision

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor.

        Uses .get() so a missing key degrades to unknown instead of raising.
        """
        value: StateType | date | datetime | Decimal = self._data.get(
            self.entity_description.data_attribute or ""
        )
        return value

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        if self.entity_description.native_unit_of_measurement:
            if self.entity_description.native_unit_of_measurement.startswith("data__"):
                uom = self.entity_description.native_unit_of_measurement[6:]
                if uom in self._data:
                    data_uom = self._data[uom]
                    if isinstance(data_uom, str):
                        return data_uom
                    _LOGGER.debug(
                        "Sensor %s: data-derived UOM %s is %r, expected str",
                        self.entity_description.key,
                        uom,
                        data_uom,
                    )
                    return None

            return self.entity_description.native_unit_of_measurement

        return None


class TrueNASUptimeSensor(TrueNASSensor):
    """Define a TrueNAS Uptime sensor."""

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        val = self._data.get(self.entity_description.data_attribute or "")
        if isinstance(val, (int, float)) and val > 0:
            return utc_from_timestamp(val)
        return None

"""Support for Poolstation sensors."""
from __future__ import annotations
import logging

from pypoolstation import Pool

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolstationDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import PoolEntity

_LOGGER = logging.getLogger(__name__)

PH_SUFFIX = " pH"
TEMPERATURE_SUFFIX = " Temperature"
SALT_SUFFIX = " Salt concentration"
ELECTROLYSIS_SUFFIX = " Electrolysis"
ORP_SUFFIX = " ORP"
FREE_CHLORINE_SUFFIX = " Chlorine"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the poolstation sensors."""
    stations = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities: list[PoolEntity] = []
    for pool_id, pool in stations.items():
        _LOGGER.warn("INITIALIZING THE SENSORS. POOL IS")
        _LOGGER.warn(pool)
        coordinator = coordinators[pool_id]
        entities.append(PoolPhSensor(pool, coordinator))
        entities.append(PoolTemperatureSensor(pool, coordinator))
        entities.append(PoolSaltConcentrationSensor(pool, coordinator))
        entities.append(PoolElectrolysisSensor(pool, coordinator))
        entities.append(PoolORPSensor(pool, coordinator))
        entities.append(PoolFreeChlorineSensor(pool, coordinator))

    async_add_entities(entities)


class PoolPhSensor(PoolEntity, SensorEntity):
    """Representation of a pool's PH sensor."""

    _attr_icon = "mdi:ph"

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the PH sensor."""
        super().__init__(pool, coordinator, PH_SUFFIX)

    @property
    def native_value(self) -> str:
        """Return the state of the PH sensor."""
        return self._pool.current_ph


class PoolTemperatureSensor(PoolEntity, SensorEntity):
    """Representation of a pool's temperature sensor."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_icon = "mdi:coolant-temperature"

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(pool, coordinator, TEMPERATURE_SUFFIX)

    @property
    def native_value(self) -> str:
        """Return the state of the temperature sensor."""
        return self._pool.temperature


class PoolSaltConcentrationSensor(PoolEntity, SensorEntity):
    """Representation of a pool's salt concentration sensor."""

    _attr_icon = "mdi:shaker"
    _attr_native_unit_of_measurement = "gr/l"

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the salt concentration sensor."""
        super().__init__(pool, coordinator, SALT_SUFFIX)

    @property
    def native_value(self) -> str:
        """Return the state of the salt concentration sensor."""
        return self._pool.salt_concentration


class PoolElectrolysisSensor(PoolEntity, SensorEntity):
    """Representation of a pool's electrolysis production sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:water-percent"

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the electrolysis production sensor."""
        super().__init__(pool, coordinator, ELECTROLYSIS_SUFFIX)

    @property
    def native_value(self) -> str:
        """Return the state of the electrolysis production sensor."""
        return self._pool.percentage_electrolysis


class PoolORPSensor(PoolEntity, SensorEntity):
    """Representation of a pool's ORP sensor."""

    _attr_icon = "mdi:atom"

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the ORP sensor."""
        super().__init__(pool, coordinator, ORP_SUFFIX)

    @property
    def native_value(self) -> str:
        """Return the state of the ORP sensor."""
        return self._pool.current_orp


class PoolFreeChlorineSensor(PoolEntity, SensorEntity):
    """Representation of a pool's free chlorine sensor."""

    _attr_icon = "mdi:cup-water"

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the free chroline sensor."""
        super().__init__(pool, coordinator, FREE_CHLORINE_SUFFIX)

    @property
    def native_value(self) -> str:
        """Return the state of the free chlorine sensor."""
        return self._pool.current_clppm

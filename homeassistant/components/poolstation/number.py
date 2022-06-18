"""Support for Poolstation numbers."""
from __future__ import annotations

from pypoolstation import Pool

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolstationDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import PoolEntity

MIN_PH = 6.0
MAX_PH = 8.0

MIN_ORP = 600
MAX_ORP = 850

MIN_CHLORINE = 0.30
MAX_CHLORINE = 3.50

TARGET_PH_SUFFIX = " Target PH"
TARGET_ORP_SUFFIX = " Target ORP"
TARGET_FREE_CHLORINE_SUFFIX = " Target Chlorine"
TARGET_ELECTROLYSIS_SUFFIX = " Target Production"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool numbers."""
    pools = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities: list[PoolEntity] = []
    for pool_id, pool in pools.items():
        coordinator = coordinators[pool_id]
        entities.append(PoolTargetPh(pool, coordinator))
        entities.append(PoolTargetElectrolysisProduction(pool, coordinator))
        entities.append(PoolTargetORP(pool, coordinator))
        entities.append(PoolTargetFreeChroline(pool, coordinator))

    async_add_entities(entities)


class PoolTargetPh(PoolEntity, NumberEntity):
    """Representation of a pool's target PH number."""

    _attr_icon = "mdi:gauge"
    _attr_max_value = MAX_PH
    _attr_min_value = MIN_PH
    _attr_step = 0.01

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the pool's target PH."""
        super().__init__(pool, coordinator, TARGET_PH_SUFFIX)

    @property
    def value(self) -> float:
        """Return the target PH."""
        return self._pool.target_ph

    async def async_set_value(self, value: float) -> None:
        """Set the target PH."""
        self._attr_value = await self._pool.set_target_ph(value)
        self.async_write_ha_state()


class PoolTargetORP(PoolEntity, NumberEntity):
    """Representation of a pool's target ORP number."""

    _attr_icon = "mdi:gauge"
    _attr_max_value = MAX_ORP
    _attr_min_value = MIN_ORP
    _attr_step = 1

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the pool's target ORP."""
        super().__init__(pool, coordinator, TARGET_ORP_SUFFIX)

    @property
    def value(self) -> float:
        """Return the target ORP."""
        return self._pool.target_orp

    async def async_set_value(self, value: float) -> None:
        """Set the target ORP."""
        self._attr_value = await self._pool.set_target_orp(value)
        self.async_write_ha_state()


class PoolTargetFreeChroline(PoolEntity, NumberEntity):
    """Representation of a pool's target free chroline number."""

    _attr_icon = "mdi:gauge"
    _attr_max_value = MAX_CHLORINE
    _attr_min_value = MIN_CHLORINE
    _attr_step = 0.01

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the pool's target chlorine."""
        super().__init__(pool, coordinator, TARGET_FREE_CHLORINE_SUFFIX)

    @property
    def value(self) -> float:
        """Return the target chlorine."""
        return self._pool.target_clppm

    async def async_set_value(self, value: float) -> None:
        """Set the target chlorine."""
        self._attr_value = await self._pool.set_target_clppm(value)
        self.async_write_ha_state()


class PoolTargetElectrolysisProduction(PoolEntity, NumberEntity):
    """Representation of a pool's target electrolysis number."""

    _attr_icon = "mdi:gauge"
    _attr_max_value = 100
    _attr_min_value = 0
    _attr_unit_of_measurement = PERCENTAGE

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the pool's target electrolysis production."""
        super().__init__(pool, coordinator, TARGET_ELECTROLYSIS_SUFFIX)

    @property
    def value(self) -> int:
        """Return the target electrolysis production."""
        return int(self._pool.target_percentage_electrolysis)

    async def async_set_value(self, value: float) -> None:
        """Set the target electrolysis production."""
        self._attr_value = await self._pool.set_target_percentage_electrolysis(
            int(value)
        )
        self.async_write_ha_state()

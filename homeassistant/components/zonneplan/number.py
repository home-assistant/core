"""Number platform for Zonneplan."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from pyzonneplan import BatteryHomeOptimization, BatteryPowerLimits

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ZonneplanBatterySettingsCoordinator, ZonneplanConfigEntry
from .entity import ZonneplanBatteryEntity, ZonneplanContractEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ZonneplanPowerLimitNumberEntityDescription(NumberEntityDescription):
    """Describes a Zonneplan home optimization power limit."""

    value_fn: Callable[[BatteryHomeOptimization], int | None]
    limits_fn: Callable[[BatteryHomeOptimization], BatteryPowerLimits | None]
    power_limits_fn: Callable[
        [BatteryHomeOptimization, int], tuple[int | None, int | None]
    ]


POWER_LIMIT_DESCRIPTIONS: tuple[ZonneplanPowerLimitNumberEntityDescription, ...] = (
    ZonneplanPowerLimitNumberEntityDescription(
        key="max_charge_power",
        translation_key="max_charge_power",
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.CONFIG,
        # The app's range when the API sends none.
        native_min_value=0,
        native_max_value=10000,
        value_fn=lambda settings: settings.max_desired_charge_power_watts,
        limits_fn=lambda settings: settings.max_desired_charge_power_limits,
        power_limits_fn=lambda settings, value: (
            value,
            settings.max_desired_discharge_power_watts,
        ),
    ),
    ZonneplanPowerLimitNumberEntityDescription(
        key="max_discharge_power",
        translation_key="max_discharge_power",
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=10000,
        value_fn=lambda settings: settings.max_desired_discharge_power_watts,
        limits_fn=lambda settings: settings.max_desired_discharge_power_limits,
        power_limits_fn=lambda settings, value: (
            settings.max_desired_charge_power_watts,
            value,
        ),
    ),
)

# The app's slider: 4 to 20 ct/kWh in steps of 1 ct.
PRICE_SPREAD_DESCRIPTION = NumberEntityDescription(
    key="price_spread",
    translation_key="price_spread",
    native_unit_of_measurement="EUR/kWh",
    entity_category=EntityCategory.CONFIG,
    native_min_value=0.04,
    native_max_value=0.2,
    native_step=0.01,
)

BACKUP_RESERVE_DESCRIPTION = NumberEntityDescription(
    key="backup_reserve",
    translation_key="backup_reserve",
    device_class=NumberDeviceClass.ENERGY_STORAGE,
    native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    native_min_value=0,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZonneplanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zonneplan number platform."""
    battery_coordinator = entry.runtime_data.battery_coordinator
    settings_coordinator = entry.runtime_data.battery_settings_coordinator

    async_add_entities(
        ZonneplanBackupReserveNumber(
            battery_coordinator, contract_uuid, BACKUP_RESERVE_DESCRIPTION
        )
        for contract_uuid, battery_data in battery_coordinator.data.items()
        if battery_data.battery.backup_power_capable
    )

    known_home_optimization: set[str] = set()
    known_day_ahead_arbitrage: set[str] = set()

    @callback
    def _async_add_settings_entities() -> None:
        """Add the numbers of the modes the batteries support, once known."""
        # Before the first successful fetch there is no data yet.
        if not settings_coordinator.last_update_success:
            return
        settings = settings_coordinator.data
        home_optimization = settings.home_optimization.keys() - known_home_optimization
        day_ahead_arbitrage = (
            settings.day_ahead_arbitrage.keys() - known_day_ahead_arbitrage
        )
        known_home_optimization.update(home_optimization)
        known_day_ahead_arbitrage.update(day_ahead_arbitrage)
        async_add_entities(
            [
                *(
                    ZonneplanPowerLimitNumber(
                        settings_coordinator,
                        contract_uuid,
                        battery_coordinator.data[contract_uuid].battery.contract,
                        description,
                    )
                    for contract_uuid in home_optimization
                    for description in POWER_LIMIT_DESCRIPTIONS
                ),
                *(
                    ZonneplanPriceSpreadNumber(
                        settings_coordinator,
                        contract_uuid,
                        battery_coordinator.data[contract_uuid].battery.contract,
                        PRICE_SPREAD_DESCRIPTION,
                    )
                    for contract_uuid in day_ahead_arbitrage
                ),
            ]
        )

    _async_add_settings_entities()
    entry.async_on_unload(
        settings_coordinator.async_add_listener(_async_add_settings_entities)
    )


class ZonneplanPowerLimitNumber(
    ZonneplanContractEntity[ZonneplanBatterySettingsCoordinator], NumberEntity
):
    """Representation of a power limit of home optimization."""

    entity_description: ZonneplanPowerLimitNumberEntityDescription

    @property
    def _settings(self) -> BatteryHomeOptimization | None:
        """Return the home optimization settings, None if the mode went away."""
        return self.coordinator.data.home_optimization.get(self._contract_uuid)

    @property
    @override
    def available(self) -> bool:
        """Return if both power limits are known, as the API takes them together."""
        return (
            super().available
            and (settings := self._settings) is not None
            and settings.max_desired_charge_power_watts is not None
            and settings.max_desired_discharge_power_watts is not None
        )

    @property
    @override
    def native_value(self) -> int | None:
        """Return the power limit."""
        return self.entity_description.value_fn(
            self.coordinator.data.home_optimization[self._contract_uuid]
        )

    def _limits(self) -> BatteryPowerLimits | None:
        """Return the power limits the API accepts, if it sent them."""
        if (settings := self._settings) is None:
            return None
        return self.entity_description.limits_fn(settings)

    @property
    @override
    def native_min_value(self) -> float:
        """Return the lowest power limit the API accepts."""
        if (limits := self._limits()) is None or limits.min_watts is None:
            return super().native_min_value
        return limits.min_watts

    @property
    @override
    def native_max_value(self) -> float:
        """Return the highest power limit the API accepts."""
        if (limits := self._limits()) is None or limits.max_watts is None:
            return super().native_max_value
        return limits.max_watts

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the power limit, keeping the other one."""
        settings = self._settings
        if TYPE_CHECKING:
            # Only reachable while available, so the settings are known.
            assert settings is not None
        max_charge_power_w, max_discharge_power_w = (
            self.entity_description.power_limits_fn(settings, int(value))
        )
        await self.coordinator.async_set_power_limits(
            self._contract_uuid, max_charge_power_w, max_discharge_power_w
        )


class ZonneplanPriceSpreadNumber(
    ZonneplanContractEntity[ZonneplanBatterySettingsCoordinator], NumberEntity
):
    """Representation of the price spread day-ahead arbitrage trades on."""

    @property
    @override
    def available(self) -> bool:
        """Return if the battery still supports day-ahead arbitrage."""
        return (
            super().available
            and self._contract_uuid in self.coordinator.data.day_ahead_arbitrage
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the price spread."""
        price_spread = self.coordinator.data.day_ahead_arbitrage[
            self._contract_uuid
        ].price_spread
        return None if price_spread is None else float(price_spread)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the price spread."""
        await self.coordinator.async_set_price_spread(self._contract_uuid, value)


class ZonneplanBackupReserveNumber(ZonneplanBatteryEntity, NumberEntity):
    """Representation of the energy a battery reserves for backup power."""

    @property
    @override
    def native_value(self) -> int | None:
        """Return the reserved energy."""
        return self.battery.reserve_discharge_cutoff_wh

    @property
    @override
    def available(self) -> bool:
        """Return if the battery reports how much energy it can reserve."""
        return (
            super().available
            and self.battery.backup_power_usable_capacity_wh is not None
        )

    @property
    @override
    def native_max_value(self) -> float:
        """Return the most energy the battery can reserve."""
        # Without a capacity the entity is unavailable.
        return self.battery.backup_power_usable_capacity_wh or 0

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the reserved energy."""
        await self.coordinator.async_set_backup_reserve(self._contract_uuid, int(value))

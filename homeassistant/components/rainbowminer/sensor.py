"""Sensor platform for the RainbowMiner integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import override

from rainbowminer_api_client import ActiveMiner, Balance, CurrentProfit

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import RainbowMinerConfigEntry, RainbowMinerCoordinator
from .entity import RainbowMinerEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def _rate(current_profit: CurrentProfit, currency: str | None) -> float | None:
    """Return the BTC->currency exchange rate, or None if unavailable."""
    if currency is None or current_profit.Rates is None:
        return None
    rate = current_profit.Rates.get(currency)
    if rate is None:
        return None
    return float(rate)


def _convert(btc_value: float | None, rate: float | None) -> float | None:
    """Convert a BTC value to the configured currency."""
    if btc_value is None or rate is None:
        return None
    return btc_value * rate


def _to_mbtc(btc_value: float | None) -> float | None:
    """Convert a BTC value to mBTC (multiply by 1000)."""
    if btc_value is None:
        return None
    return float(btc_value) * 1000


def _power(current_profit: CurrentProfit) -> float | int | None:
    """Return the total power draw in watts, or None if unavailable.

    The API returns a single number or a dict of CPU/GPU/Offset values.
    """
    power = current_profit.Power
    if isinstance(power, dict):
        return sum(value for value in power.values() if isinstance(value, int | float))
    return power


def _sum_btc(balances: list[Balance], field: str) -> float | None:
    """Sum a _BTC field across all balance entries.

    Returns None if no entries have a value for the field.
    """
    total = 0.0
    found = False
    for balance in balances:
        value = getattr(balance, field, None)
        if value is None:
            continue
        total += float(value)
        found = True
    return total if found else None


def _format_uptime(seconds: int) -> str:
    """Format uptime seconds into a human-readable string.

    Uses 365 days/year and 30 days/month approximations.
    Omits leading zero-value components (e.g. "1 day, 2 hours" not "0 years, 0 months, 1 day, 2 hours").
    """
    if seconds <= 0:
        return "0 sec"

    years, rem = divmod(seconds, 365 * 86400)
    months, rem = divmod(rem, 30 * 86400)
    days, rem = divmod(rem, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts: list[str] = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} min")
    if secs:
        parts.append(f"{secs} sec")

    return ", ".join(parts) if parts else "0 sec"


def _active_pool_names(miners: list[ActiveMiner]) -> str | None:
    """Return a deduplicated, comma-joined list of pool names from running miners.

    Only miners with Status 0 (running) are considered. The Pool field can be
    a string or a list of strings.
    Truncates to 255 characters to satisfy Home Assistant's state length limit.
    """
    seen: set[str] = set()
    names: list[str] = []
    for miner in miners:
        if getattr(miner, "Status", None) != 0:
            continue
        pools = getattr(miner, "Pool", None)
        if pools is None:
            continue
        if isinstance(pools, str):
            pools = [pools]
        for pool in pools:
            if pool and pool not in seen:
                seen.add(pool)
                names.append(pool)
    if not names:
        return None
    result = ", ".join(names)
    if len(result) <= 255:
        return result
    return result[:252] + "..."


@dataclass(frozen=True, kw_only=True)
class RainbowMinerSensorEntityDescription(SensorEntityDescription):
    """Description of a RainbowMiner sensor."""

    value_fn: Callable[[RainbowMinerCoordinator, str | None], StateType]


ALWAYS_SENSORS: tuple[RainbowMinerSensorEntityDescription, ...] = (
    RainbowMinerSensorEntityDescription(
        key="active_miners",
        translation_key="active_miners",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coord, _cur: sum(
            1 for m in coord.data.active_miners if getattr(m, "Status", None) == 0
        ),
    ),
    RainbowMinerSensorEntityDescription(
        key="active_pools",
        translation_key="active_pools",
        value_fn=lambda coord, _cur: _active_pool_names(coord.data.active_miners),
    ),
    RainbowMinerSensorEntityDescription(
        key="total_earnings_mbtc",
        translation_key="total_earnings_mbtc",
        native_unit_of_measurement="mBTC",
        value_fn=lambda coord, _cur: _to_mbtc(
            _sum_btc(coord.data.balances, "Earnings_BTC")
        ),
    ),
    RainbowMinerSensorEntityDescription(
        key="unpaid_balance_mbtc",
        translation_key="unpaid_balance_mbtc",
        native_unit_of_measurement="mBTC",
        value_fn=lambda coord, _cur: _to_mbtc(
            _sum_btc(coord.data.balances, "Total_BTC")
        ),
    ),
    RainbowMinerSensorEntityDescription(
        key="estimated_daily_profit_mbtc",
        translation_key="estimated_daily_profit_mbtc",
        native_unit_of_measurement="mBTC",
        value_fn=lambda coord, _cur: _to_mbtc(coord.data.current_profit.AllProfitBTC),
    ),
    RainbowMinerSensorEntityDescription(
        key="weekly_earnings_mbtc",
        translation_key="weekly_earnings_mbtc",
        native_unit_of_measurement="mBTC",
        value_fn=lambda coord, _cur: _to_mbtc(
            _sum_btc(coord.data.balances, "Earnings_1w_BTC")
        ),
    ),
    RainbowMinerSensorEntityDescription(
        key="daily_earnings_mbtc",
        translation_key="daily_earnings_mbtc",
        native_unit_of_measurement="mBTC",
        value_fn=lambda coord, _cur: _to_mbtc(
            _sum_btc(coord.data.balances, "Earnings_1d_BTC")
        ),
    ),
    RainbowMinerSensorEntityDescription(
        key="hourly_earnings_mbtc",
        translation_key="hourly_earnings_mbtc",
        native_unit_of_measurement="mBTC",
        value_fn=lambda coord, _cur: _to_mbtc(
            _sum_btc(coord.data.balances, "Earnings_1h_BTC")
        ),
    ),
    RainbowMinerSensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coord, _cur: _power(coord.data.current_profit),
    ),
    RainbowMinerSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coord, _cur: coord.data.uptime.Seconds,
    ),
    RainbowMinerSensorEntityDescription(
        key="version",
        translation_key="version",
        value_fn=lambda coord, _cur: coord.data.version.version_string(),
    ),
)


def currency_sensors(
    currency: str,
) -> tuple[RainbowMinerSensorEntityDescription, ...]:
    """Return earnings sensors in the configured currency."""
    return (
        RainbowMinerSensorEntityDescription(
            key="total_earnings",
            translation_key="total_earnings",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement=currency,
            value_fn=lambda coord, cur: _convert(
                _sum_btc(coord.data.balances, "Earnings_BTC"),
                _rate(coord.data.current_profit, cur),
            ),
        ),
        RainbowMinerSensorEntityDescription(
            key="unpaid_balance",
            translation_key="unpaid_balance",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement=currency,
            value_fn=lambda coord, cur: _convert(
                _sum_btc(coord.data.balances, "Total_BTC"),
                _rate(coord.data.current_profit, cur),
            ),
        ),
        RainbowMinerSensorEntityDescription(
            key="estimated_daily_profit",
            translation_key="estimated_daily_profit",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement=currency,
            value_fn=lambda coord, cur: _convert(
                coord.data.current_profit.AllProfitBTC,
                _rate(coord.data.current_profit, cur),
            ),
        ),
        RainbowMinerSensorEntityDescription(
            key="weekly_earnings",
            translation_key="weekly_earnings",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement=currency,
            value_fn=lambda coord, cur: _convert(
                _sum_btc(coord.data.balances, "Earnings_1w_BTC"),
                _rate(coord.data.current_profit, cur),
            ),
        ),
        RainbowMinerSensorEntityDescription(
            key="daily_earnings",
            translation_key="daily_earnings",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement=currency,
            value_fn=lambda coord, cur: _convert(
                _sum_btc(coord.data.balances, "Earnings_1d_BTC"),
                _rate(coord.data.current_profit, cur),
            ),
        ),
        RainbowMinerSensorEntityDescription(
            key="hourly_earnings",
            translation_key="hourly_earnings",
            device_class=SensorDeviceClass.MONETARY,
            native_unit_of_measurement=currency,
            value_fn=lambda coord, cur: _convert(
                _sum_btc(coord.data.balances, "Earnings_1h_BTC"),
                _rate(coord.data.current_profit, cur),
            ),
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainbowMinerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RainbowMiner sensors."""
    coordinator = entry.runtime_data
    currency = hass.config.currency
    descriptions: list[RainbowMinerSensorEntityDescription] = list(ALWAYS_SENSORS)
    if currency is not None:
        descriptions.extend(currency_sensors(currency))
    entities: list[RainbowMinerSensor | RainbowMinerUptimeSensor] = []
    for description in descriptions:
        if description.key == "uptime":
            entities.append(
                RainbowMinerUptimeSensor(coordinator, description, currency)
            )
        else:
            entities.append(RainbowMinerSensor(coordinator, description, currency))
    async_add_entities(entities)


class RainbowMinerSensor(RainbowMinerEntity, SensorEntity):
    """Representation of a RainbowMiner sensor."""

    entity_description: RainbowMinerSensorEntityDescription

    def __init__(
        self,
        coordinator: RainbowMinerCoordinator,
        description: RainbowMinerSensorEntityDescription,
        currency: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)
        self._currency = currency

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor's native value."""
        return self.entity_description.value_fn(self.coordinator, self._currency)


class RainbowMinerUptimeSensor(RainbowMinerSensor):
    """RainbowMiner uptime sensor with a formatted duration attribute."""

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, str] | None:
        """Return the formatted uptime string."""
        seconds = self.coordinator.data.uptime.Seconds
        if seconds is None:
            return None
        return {"formatted": _format_uptime(seconds)}

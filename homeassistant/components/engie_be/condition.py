"""Automation conditions for the ENGIE Belgium integration."""

from abc import abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, Unpack, override

from aioengiebelgium import EpexGranularity
import probatio

from homeassistant.const import ATTR_DEVICE_ID, CONF_ABOVE, CONF_BELOW
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckParams,
    ConditionConfig,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .coordinator import epex_price_at
from .helpers import (
    DEVICE_IDS_OPTIONS_SCHEMA,
    THRESHOLD_OPTIONS_SCHEMA,
    async_get_device_epex_data,
    async_validate_epex_options,
    price_in_range,
)


class _EpexCondition(Condition):
    """Base for conditions on the current EPEX price of ENGIE Belgium devices.

    The condition passes when every selected device has a dynamic tariff,
    known EPEX prices and a current price that passes the check.
    """

    _options_schema: probatio.Schema = DEVICE_IDS_OPTIONS_SCHEMA
    _granularity: EpexGranularity

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return async_validate_epex_options(hass, config, cls._options_schema)

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._options: dict[str, Any] = config.options
        self._device_ids: list[str] = config.options[ATTR_DEVICE_ID]

    @abstractmethod
    def _check_price(self, price: float) -> bool:
        """Return True when the current price passes the check."""

    def _check_device(self, device_id: str, now: datetime) -> bool:
        """Return True when the current price of one device passes the check."""
        data = async_get_device_epex_data(self._hass, device_id)
        if data is None:
            return False
        price = epex_price_at(data, self._granularity, now)
        return price is not None and self._check_price(price)

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        now = dt_util.utcnow()
        return all(self._check_device(device_id, now) for device_id in self._device_ids)


class _EpexNegativeCondition(_EpexCondition):
    """Base for conditions that pass while the current EPEX price is negative."""

    @override
    def _check_price(self, price: float) -> bool:
        """Return True when the price is negative."""
        return price < 0


class _EpexThresholdCondition(_EpexCondition):
    """Base for conditions that pass while the current EPEX price is in a range."""

    _options_schema = THRESHOLD_OPTIONS_SCHEMA

    @override
    def _check_price(self, price: float) -> bool:
        """Return True when the price is inside the range."""
        return price_in_range(
            price, self._options.get(CONF_ABOVE), self._options.get(CONF_BELOW)
        )


class EpexHourPriceIsNegativeCondition(_EpexNegativeCondition):
    """Condition that passes while the hourly EPEX price is negative."""

    _granularity = EpexGranularity.HOURLY


class EpexQuarterHourPriceIsNegativeCondition(_EpexNegativeCondition):
    """Condition that passes while the quarter-hourly EPEX price is negative."""

    _granularity = EpexGranularity.QUARTER_HOURLY


class EpexHourPriceMeetsThresholdCondition(_EpexThresholdCondition):
    """Condition that passes while the hourly EPEX price is in a range."""

    _granularity = EpexGranularity.HOURLY


class EpexQuarterHourPriceMeetsThresholdCondition(_EpexThresholdCondition):
    """Condition that passes while the quarter-hourly EPEX price is in a range."""

    _granularity = EpexGranularity.QUARTER_HOURLY


CONDITIONS: dict[str, type[Condition]] = {
    "epex_hour_price_is_negative": EpexHourPriceIsNegativeCondition,
    "epex_hour_price_meets_threshold": EpexHourPriceMeetsThresholdCondition,
    "epex_quarter_hour_price_is_negative": EpexQuarterHourPriceIsNegativeCondition,
    "epex_quarter_hour_price_meets_threshold": (
        EpexQuarterHourPriceMeetsThresholdCondition
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for the ENGIE Belgium integration."""
    return CONDITIONS

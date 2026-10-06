"""Offer date based automation conditions."""

from typing import Unpack, cast, override

import probatio

from homeassistant.const import CONF_END, CONF_OPTIONS, CONF_START
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckParams,
    ConditionConfig,
    condition_trace_update_result,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

type MonthDay = tuple[int, int]

_DATE_CONDITION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OPTIONS): probatio.All(
            {
                probatio.Optional(CONF_START): cv.month_day,
                probatio.Optional(CONF_END): cv.month_day,
            },
            probatio.AtLeastOne(CONF_START, CONF_END),
        )
    }
)


def _format_month_day(month_day: MonthDay) -> str:
    """Format a (month, day) tuple as MM-DD."""
    return f"{month_day[0]:02d}-{month_day[1]:02d}"


class DateCondition(Condition):
    """Test if the local date is within a yearly recurring range.

    Both ends are inclusive. A range whose start is after its end wraps
    around the turn of the year, e.g. 12-24 until 01-06.
    """

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _DATE_CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        assert config.options is not None
        self._start: MonthDay = config.options.get(CONF_START, (1, 1))
        self._end: MonthDay = config.options.get(CONF_END, (12, 31))

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        today = dt_util.now().date()
        now_month_day = (today.month, today.day)

        condition_trace_update_result(
            start=_format_month_day(self._start),
            now_date=today.isoformat(),
            end=_format_month_day(self._end),
        )
        if self._start <= self._end:
            return self._start <= now_month_day <= self._end
        return now_month_day >= self._start or now_month_day <= self._end


CONDITIONS: dict[str, type[Condition]] = {
    "date": DateCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the Home Assistant conditions."""
    return CONDITIONS

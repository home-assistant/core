"""Service calls for the Tesla Fleet integration."""

from copy import deepcopy
from datetime import date, time
from itertools import pairwise
from math import isfinite
from typing import Any

from tesla_fleet_api.const import Scope
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_NAME, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util import slugify

from .const import DOMAIN
from .helpers import handle_command
from .models import TeslaFleetEnergyData

ATTR_BUY_RATE = "buy_rate"
ATTR_DAILY_CHARGE = "daily_charge"
ATTR_DAYS = "days"
ATTR_END_DAY = "end_day"
ATTR_END_MONTH = "end_month"
ATTR_END_TIME = "end_time"
ATTR_PERIODS = "periods"
ATTR_SEASONS = "seasons"
ATTR_SELL_RATE = "sell_rate"
ATTR_START_DAY = "start_day"
ATTR_START_MONTH = "start_month"
ATTR_START_TIME = "start_time"
ATTR_UTILITY = "utility"

SERVICE_TIME_OF_USE = "time_of_use"

DAY_TO_TESLA = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
SEASON_DATE_FIELDS = frozenset(
    {ATTR_START_MONTH, ATTR_START_DAY, ATTR_END_MONTH, ATTR_END_DAY}
)
# Tesla's charge trees carry a reserved "ALL" fallback entry, so no season may
# use that name.
ALL_SEASON = "ALL"
# A year-round tariff is sent the way the Tesla app stores one: a "Summer"
# season covering the whole year plus an empty "Winter". Tesla accepts other
# shapes (e.g. a season keyed "ALL") but then doesn't act on the tariff.
YEAR_ROUND_SEASON = "Summer"
EMPTY_SEASON = "Winter"
# Tesla only acts on its canonical time-of-use labels, assigned here by import
# rate from cheapest to dearest. Free-form labels are stored but ignored.
TESLA_LABELS: dict[int, tuple[str, ...]] = {
    1: ("OFF_PEAK",),
    2: ("OFF_PEAK", "ON_PEAK"),
    3: ("OFF_PEAK", "PARTIAL_PEAK", "ON_PEAK"),
    4: ("SUPER_OFF_PEAK", "OFF_PEAK", "PARTIAL_PEAK", "ON_PEAK"),
}


def async_get_device_for_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> dr.DeviceEntry:
    """Get the device entry related to a service call."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(hass)
    # An energy site is a full device entry; a child device cannot be a target.
    if not isinstance(
        device_entry := device_registry.async_get(device_id), dr.DeviceEntry
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device",
            translation_placeholders={"device_id": device_id},
        )

    return device_entry


def async_get_config_for_device(
    hass: HomeAssistant, device_entry: dr.DeviceEntry
) -> ConfigEntry:
    """Get the config entry related to a device entry."""
    entry = hass.config_entries.async_get_known_entry(device_entry.config_entry_id)
    if entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device",
            translation_placeholders={"device_id": device_entry.id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    return entry


def async_get_energy_site_for_entry(
    hass: HomeAssistant, device: dr.DeviceEntry, config: ConfigEntry
) -> TeslaFleetEnergyData:
    """Get the energy site data for a config entry."""
    for energysite in config.runtime_data.energysites:
        if str(energysite.id) == device.serial_number:
            return energysite
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
        translation_placeholders={"device_id": device.id},
    )


def _finite_float(value: Any) -> float:
    """Validate a finite number."""
    result = vol.Coerce(float)(value)
    if not isfinite(result):
        raise vol.Invalid("Rate must be a finite number")
    return result


def _non_empty_string(value: Any) -> str:
    """Validate a string that is not blank."""
    if not (result := cv.string(value).strip()):
        raise vol.Invalid("Value must not be empty")
    return result


def _whole_minute(value: Any) -> time:
    """Validate a time Tesla can express, which is only hours and minutes."""
    result = cv.time(value)
    if result.second or result.microsecond:
        raise vol.Invalid("Times must fall on a whole minute")
    return result


def _period_key(name: str) -> str:
    """Normalise a period name so differently cased spellings match."""
    if not (key := slugify(name).upper()):
        raise vol.Invalid(f"Unable to derive a tariff label from {name!r}")
    return key


def _period_labels(season: dict[str, Any]) -> dict[str, str]:
    """Map a season's period names to Tesla labels, cheapest import rate first.

    Labels are assigned per season, so OFF_PEAK is always the cheaper rate
    within the season it prices, whatever the other seasons charge.
    """
    rates: dict[str, float] = {}
    for period in season[ATTR_PERIODS]:
        rates.setdefault(_period_key(period[ATTR_NAME]), period[ATTR_BUY_RATE])
    if len(rates) > len(TESLA_LABELS):
        raise vol.Invalid(
            f"Tesla supports at most {len(TESLA_LABELS)} distinct periods per "
            f"season, {season[ATTR_NAME]!r} has {len(rates)}"
        )
    ordered = sorted(rates, key=lambda key: rates[key])
    return dict(zip(ordered, TESLA_LABELS[len(ordered)], strict=True))


def _whole_number(value: Any) -> int:
    """Validate a whole number, since truncating one would move a season."""
    if isinstance(value, bool):
        raise vol.Invalid("Value must be a whole number")
    if isinstance(value, float):
        if not value.is_integer():
            raise vol.Invalid("Value must be a whole number")
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except ValueError:
        raise vol.Invalid("Value must be a whole number") from None


def _validate_period(period: dict[str, Any]) -> dict[str, Any]:
    """Validate a single rate period."""
    if (ATTR_START_TIME in period) != (ATTR_END_TIME in period):
        raise vol.Invalid("start_time and end_time must be provided together")
    return period


TOU_PERIOD_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_NAME): _non_empty_string,
            vol.Optional(ATTR_DAYS): vol.All(cv.ensure_list, [vol.In(DAY_TO_TESLA)]),
            vol.Optional(ATTR_START_TIME): _whole_minute,
            vol.Optional(ATTR_END_TIME): _whole_minute,
            vol.Required(ATTR_BUY_RATE): _finite_float,
            vol.Optional(ATTR_SELL_RATE): _finite_float,
        }
    ),
    _validate_period,
)

TOU_SEASON_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): _non_empty_string,
        vol.Optional(ATTR_START_MONTH): vol.All(
            _whole_number, vol.Range(min=1, max=12)
        ),
        vol.Optional(ATTR_START_DAY): vol.All(_whole_number, vol.Range(min=1, max=31)),
        vol.Optional(ATTR_END_MONTH): vol.All(_whole_number, vol.Range(min=1, max=12)),
        vol.Optional(ATTR_END_DAY): vol.All(_whole_number, vol.Range(min=1, max=31)),
        vol.Required(ATTR_PERIODS): vol.All(
            cv.ensure_list, vol.Length(min=1), [TOU_PERIOD_SCHEMA]
        ),
    }
)


MINUTES_PER_DAY = 24 * 60


def _period_spans(period: dict[str, Any]) -> dict[int, list[tuple[int, int]]]:
    """Return the half-open minute spans a period covers, keyed by weekday.

    A period ending at or before it starts runs through midnight, so its
    remainder lands on the following weekday.
    """
    start: time = period.get(ATTR_START_TIME, time())
    end: time = period.get(ATTR_END_TIME, time())
    first = start.hour * 60 + start.minute
    last = end.hour * 60 + end.minute

    spans: dict[int, list[tuple[int, int]]] = {}
    for name in period.get(ATTR_DAYS) or list(DAY_TO_TESLA):
        day = DAY_TO_TESLA[name]
        if first == last:
            spans.setdefault(day, []).append((0, MINUTES_PER_DAY))
        elif last < first:
            spans.setdefault(day, []).append((first, MINUTES_PER_DAY))
            spans.setdefault((day + 1) % len(DAY_TO_TESLA), []).append((0, last))
        else:
            spans.setdefault(day, []).append((first, last))
    return spans


def _check_period_overlaps(season: dict[str, Any]) -> None:
    """Reject periods that price the same weekday and minute twice."""
    by_day: dict[int, list[tuple[int, int, str]]] = {}
    for period in season[ATTR_PERIODS]:
        for day, spans in _period_spans(period).items():
            for first, last in spans:
                by_day.setdefault(day, []).append((first, last, period[ATTR_NAME]))

    for day_spans in by_day.values():
        day_spans.sort()
        for (_, earlier_end, earlier), (later_start, _, later) in pairwise(day_spans):
            if later_start < earlier_end:
                raise vol.Invalid(
                    f"Periods {earlier!r} and {later!r} overlap in "
                    f"{season[ATTR_NAME]!r}"
                )


def _season_spans(season: dict[str, Any]) -> list[tuple[int, int]]:
    """Return the half-open day-of-year spans a season covers."""
    first = date(2000, season[ATTR_START_MONTH], season[ATTR_START_DAY]).timetuple()
    last = date(2000, season[ATTR_END_MONTH], season[ATTR_END_DAY]).timetuple()
    if last.tm_yday < first.tm_yday:
        return [(first.tm_yday, 367), (1, last.tm_yday + 1)]
    return [(first.tm_yday, last.tm_yday + 1)]


def _check_season_overlaps(seasons: list[dict[str, Any]]) -> None:
    """Reject seasons that cover the same date."""
    spans: list[tuple[int, int, str]] = [
        (first, last, season[ATTR_NAME])
        for season in seasons
        for first, last in _season_spans(season)
    ]
    spans.sort()
    for (_, earlier_end, earlier), (later_start, _, later) in pairwise(spans):
        if later_start < earlier_end:
            raise vol.Invalid(f"Seasons {earlier!r} and {later!r} overlap")


def _validate_seasons(seasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate season dates, label collisions and export rate coverage."""
    for season in seasons:
        if season[ATTR_NAME] == ALL_SEASON:
            raise vol.Invalid(
                f"{ALL_SEASON} is reserved by Tesla and cannot name a season"
            )

    if not _is_year_round(seasons):
        season_names: set[str] = set()
        for season in seasons:
            # Dates may only be omitted by a lone season covering the whole year.
            if SEASON_DATE_FIELDS.difference(season):
                raise vol.Invalid(
                    "Every season needs a start and end month and day unless it "
                    "is the only season and applies all year"
                )
            # A season may wrap the new year, so only each endpoint is checked.
            for month, day in (
                (season[ATTR_START_MONTH], season[ATTR_START_DAY]),
                (season[ATTR_END_MONTH], season[ATTR_END_DAY]),
            ):
                try:
                    date(2000, month, day)
                except ValueError as err:
                    raise vol.Invalid(f"Invalid season date {day}/{month}") from err
            if season[ATTR_NAME] in season_names:
                raise vol.Invalid(f"Duplicate season name {season[ATTR_NAME]!r}")
            season_names.add(season[ATTR_NAME])

        _check_season_overlaps(seasons)

    periods = [period for season in seasons for period in season[ATTR_PERIODS]]
    if any(ATTR_SELL_RATE in period for period in periods) and any(
        ATTR_SELL_RATE not in period for period in periods
    ):
        raise vol.Invalid(
            "sell_rate must be set on every period when export rates are used"
        )

    for season in seasons:
        labels: dict[str, str] = {}
        rates: dict[str, tuple[float, float | None]] = {}
        for period in season[ATTR_PERIODS]:
            key = _period_key(period[ATTR_NAME])
            if labels.setdefault(key, period[ATTR_NAME]) != period[ATTR_NAME]:
                raise vol.Invalid(
                    f"Period names {labels[key]!r} and {period[ATTR_NAME]!r} both "
                    f"produce the tariff label {key}"
                )
            # Tesla holds one rate per label, so a period split across several
            # times of day has to charge the same rate each time.
            rate = (period[ATTR_BUY_RATE], period.get(ATTR_SELL_RATE))
            if rates.setdefault(key, rate) != rate:
                raise vol.Invalid(
                    f"Period {period[ATTR_NAME]!r} is used more than once in "
                    f"{season[ATTR_NAME]!r} with different rates"
                )

        _check_period_overlaps(season)
        _period_labels(season)

    return seasons


TIME_OF_USE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(ATTR_NAME): _non_empty_string,
        vol.Required(ATTR_UTILITY): _non_empty_string,
        vol.Optional(ATTR_DAILY_CHARGE): vol.All(_finite_float, vol.Range(min=0)),
        vol.Required(ATTR_SEASONS): vol.All(
            cv.ensure_list, vol.Length(min=1), [TOU_SEASON_SCHEMA], _validate_seasons
        ),
    }
)


def _is_year_round(seasons: list[dict[str, Any]]) -> bool:
    """Return True when the tariff is a single season with no dates."""
    return len(seasons) == 1 and not SEASON_DATE_FIELDS.intersection(seasons[0])


def _tesla_day_ranges(days: list[str] | None) -> list[tuple[int, int]]:
    """Convert selected weekdays into contiguous Tesla day ranges."""
    if not days:
        return [(0, 6)]

    numbers = sorted({DAY_TO_TESLA[day] for day in days})
    ranges: list[tuple[int, int]] = []
    start = end = numbers[0]
    for number in numbers[1:]:
        if number == end + 1:
            end = number
            continue
        ranges.append((start, end))
        start = end = number
    ranges.append((start, end))

    # Tesla ranges may wrap the weekend, so join Sunday back onto Monday.
    if len(ranges) > 1 and ranges[0][0] == 0 and ranges[-1][1] == 6:
        ranges = [(ranges[-1][0], ranges[0][1]), *ranges[1:-1]]

    return ranges


def _build_seasons(
    seasons: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build the Tesla seasons tree and the import and export energy charges."""
    year_round = _is_year_round(seasons)
    tesla_seasons: dict[str, Any] = {}
    buy_charges: dict[str, Any] = {ALL_SEASON: {"rates": {ALL_SEASON: 0}}}
    sell_charges: dict[str, Any] = {ALL_SEASON: {"rates": {ALL_SEASON: 0}}}
    has_sell = False

    for season in seasons:
        key = YEAR_ROUND_SEASON if year_round else season[ATTR_NAME]
        labels = _period_labels(season)
        tou_periods: dict[str, Any] = {}
        buy_rates: dict[str, float] = {}
        sell_rates: dict[str, float] = {}

        for period in season[ATTR_PERIODS]:
            label = labels[_period_key(period[ATTR_NAME])]
            buy_rates[label] = period[ATTR_BUY_RATE]
            if ATTR_SELL_RATE in period:
                sell_rates[label] = period[ATTR_SELL_RATE]

            start: time = period.get(ATTR_START_TIME, time())
            end: time = period.get(ATTR_END_TIME, time())
            entries = tou_periods.setdefault(label, {"periods": []})["periods"]
            entries.extend(
                {
                    "fromDayOfWeek": from_day,
                    "toDayOfWeek": to_day,
                    "fromHour": start.hour,
                    "fromMinute": start.minute,
                    "toHour": end.hour,
                    "toMinute": end.minute,
                }
                for from_day, to_day in _tesla_day_ranges(period.get(ATTR_DAYS))
            )

        if year_round:
            dates = {"fromMonth": 1, "fromDay": 1, "toMonth": 12, "toDay": 31}
        else:
            dates = {
                "fromMonth": season[ATTR_START_MONTH],
                "fromDay": season[ATTR_START_DAY],
                "toMonth": season[ATTR_END_MONTH],
                "toDay": season[ATTR_END_DAY],
            }

        tesla_seasons[key] = {**dates, "tou_periods": tou_periods}
        buy_charges[key] = {"rates": buy_rates}
        sell_charges[key] = {"rates": sell_rates}
        has_sell = has_sell or bool(sell_rates)

    if year_round:
        tesla_seasons[EMPTY_SEASON] = {}
        buy_charges[EMPTY_SEASON] = {}
        sell_charges[EMPTY_SEASON] = {}

    return tesla_seasons, buy_charges, sell_charges if has_sell else {}


def build_tariff_content_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Build a Tesla tariff_content_v2 payload from the action input.

    The shape mirrors a tariff created in the Tesla app (as returned by
    site_info): no version, currency or unused charge fields, canonical
    labels, and a reserved "ALL" fallback in each charge tree.
    """
    seasons, buy_charges, sell_charges = _build_seasons(data[ATTR_SEASONS])
    demand_charges: dict[str, Any] = {ALL_SEASON: {"rates": {ALL_SEASON: 0}}}
    demand_charges |= {key: {} for key in seasons}
    daily_charge: dict[str, Any] = {"name": "Charge"}
    if data.get(ATTR_DAILY_CHARGE):
        daily_charge["amount"] = data[ATTR_DAILY_CHARGE]

    tariff: dict[str, Any] = {
        "code": "home_assistant",
        "name": data[ATTR_NAME],
        "utility": data[ATTR_UTILITY],
        "daily_charges": [daily_charge],
        "demand_charges": demand_charges,
        "energy_charges": buy_charges,
        "seasons": seasons,
    }

    if sell_charges:
        tariff["sell_tariff"] = {
            "name": data[ATTR_NAME],
            "utility": data[ATTR_UTILITY],
            "daily_charges": [{"name": "Charge"}],
            "demand_charges": deepcopy(demand_charges),
            "energy_charges": sell_charges,
            "seasons": deepcopy(seasons),
        }

    return tariff


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Tesla Fleet services."""

    async def time_of_use(call: ServiceCall) -> None:
        """Configure time-of-use settings on an energy site."""
        device = async_get_device_for_service_call(hass, call)
        config = async_get_config_for_device(hass, device)
        site = async_get_energy_site_for_entry(hass, device, config)
        if Scope.ENERGY_CMDS not in config.runtime_data.scopes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="missing_scope_energy_cmds",
            )
        if not site.info_coordinator.data.get("components_tou_capable"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="site_not_tou_capable",
            )

        resp = await handle_command(
            site.api.time_of_use_settings(build_tariff_content_v2(call.data))
        )
        if error := resp.get("error"):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={"error": error},
            )

    # Replacing the tariff changes how the battery is billed, so keep it to admins.
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_TIME_OF_USE,
        time_of_use,
        schema=TIME_OF_USE_SCHEMA,
    )

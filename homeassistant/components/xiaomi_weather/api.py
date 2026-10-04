"""Asynchronous Xiaomi weather client, independent of Home Assistant.

The endpoint is used by Xiaomi Weather and is not a documented public API.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import math
import re
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

URL = "https://weatherapi.market.xiaomi.com/wtr-v3/weather/all"
LOCATION_URL = "https://weatherapi.market.xiaomi.com/wtr-v3/location/city"
CONDITIONS = {
    "0": "sunny",
    "1": "partlycloudy",
    "2": "cloudy",
    "3": "rainy",
    "4": "lightning-rainy",
    "5": "hail",
    "6": "snowy-rainy",
    "7": "rainy",
    "8": "rainy",
    "9": "pouring",
    "10": "pouring",
    "11": "pouring",
    "12": "pouring",
    "13": "snowy",
    "14": "snowy",
    "15": "snowy",
    "16": "snowy",
    "17": "snowy",
    "18": "fog",
    "19": "snowy-rainy",
    "20": "exceptional",
    "21": "rainy",
    "22": "pouring",
    "23": "pouring",
    "24": "pouring",
    "25": "pouring",
    "26": "snowy",
    "27": "snowy",
    "28": "snowy",
    "29": "exceptional",
    "30": "exceptional",
    "31": "exceptional",
    "53": "fog",
}


class XiaomiWeatherError(Exception):
    """A transport or invalid response error."""


@dataclass(frozen=True, slots=True)
class ForecastData:
    """One forecast period in Celsius and UTC."""

    time: datetime
    temperature: float
    low: float | None
    condition: str | None
    wind_speed: float | None = None
    wind_bearing: float | None = None
    precipitation_probability: int | None = None
    is_daytime: bool | None = None


@dataclass(frozen=True, slots=True)
class WeatherData:
    """Validated snapshot; optional measurements may be unavailable."""

    temperature: float
    condition: str | None
    humidity: float | None
    pressure: float | None
    wind_speed: float | None
    wind_bearing: float | None
    apparent_temperature: float | None
    uv_index: float | None
    daily: tuple[ForecastData, ...]
    hourly: tuple[ForecastData, ...]
    visibility: float | None
    twice_daily: tuple[ForecastData, ...]


def number(value: object) -> float | None:
    """Accept finite numeric values, preserving zero and rejecting sentinels."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        result = float(value)
    except ValueError, OverflowError:
        return None
    return result if math.isfinite(result) and result != -999 else None


def timestamp(value: str) -> datetime:
    """Require an explicit timezone; never assume the HA server timezone."""
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Missing timezone")
    return result.astimezone(UTC)


def condition(code: object, time: datetime, suns: list[Any]) -> str | None:
    """Resolve clear nights from the forecast location's sunrise and sunset."""
    result = CONDITIONS.get(str(code))
    if result == "sunny":
        for sun in suns:
            sun = block(sun)
            rise = optional_time(sun.get("from"))
            setting = optional_time(sun.get("to"))
            if rise is None or setting is None:
                continue
            local_zone = datetime.fromisoformat(sun["from"]).tzinfo
            if time.astimezone(local_zone).date() == rise.astimezone(local_zone).date():
                return "sunny" if rise <= time < setting else "clear-night"
    return result


def block(value: Any) -> dict[str, Any]:
    """Isolate missing or failed optional blocks from the current weather."""
    return value if isinstance(value, dict) and value.get("status", 0) == 0 else {}


def optional_time(value: Any) -> datetime | None:
    """Do not invent timestamps for optional data."""
    if not isinstance(value, str):
        return None
    try:
        return timestamp(value)
    except ValueError, OverflowError:
        return None


def series_items(value: Any) -> list[Any]:
    """Return a valid optional array without failing other measurements."""
    items = block(value).get("value")
    return items if isinstance(items, list) else []


def daily_value(series: Any, index: int, part: str | None = None) -> Any:
    """Read a parallel daily field without shifting gaps."""
    items = series_items(series)
    value = items[index] if index < len(items) else None
    return block(value).get(part) if part is not None else value


def daily_wind(daily: dict[str, Any], index: int, part: str, key: str) -> float | None:
    """Daily wind has explicit units, unlike the legacy hourly array."""
    series = block(block(daily.get("wind")).get(key))
    unit = "km/h" if key == "speed" else "°"
    if series.get("unit") != unit:
        return None
    return number(daily_value(series, index, part))


def probability(value: Any) -> int | None:
    """Weathercn daily probabilities are percentages, never infer a fraction."""
    result = number(value)
    return round(result) if result is not None and 0 <= result <= 100 else None


def hourly_winds(hourly: dict[str, Any]) -> dict[datetime, dict[str, Any]]:
    """Join wind by its own timestamp, not the temperature array position."""
    return {
        time: item
        for item in series_items(hourly.get("wind"))
        if isinstance(item, dict)
        and (time := optional_time(item.get("datetime"))) is not None
    }


def parse_weather(payload: Any) -> WeatherData:
    """Validate required data and normalize the provider's parallel arrays."""
    try:
        current = payload["current"]
        temp = measurement(current.get("temperature", {}), "℃")
        if temp is None:
            raise XiaomiWeatherError("Missing current temperature")
        now = timestamp(current["pubTime"])
        daily = block(payload.get("forecastDaily"))
        suns = series_items(daily.get("sunRiseSet"))
        days: list[ForecastData] = []
        twice_daily: list[ForecastData] = []
        temperatures = block(daily.get("temperature"))
        if temperatures.get("unit") == "℃":
            for index, item in enumerate(series_items(temperatures)):
                item = block(item)
                high, low = number(item.get("from")), number(item.get("to"))
                sun = block(suns[index]) if index < len(suns) else {}
                if high is not None and optional_time(sun.get("from")) is not None:
                    local = datetime.fromisoformat(sun["from"])
                    date = timestamp(
                        local.replace(hour=0, minute=0, second=0).isoformat()
                    )
                    code = daily_value(daily.get("weather"), index, "from")
                    days.append(
                        ForecastData(
                            date,
                            high,
                            low,
                            CONDITIONS.get(str(code)),
                            daily_wind(daily, index, "from", "speed"),
                            daily_wind(daily, index, "from", "direction"),
                            probability(
                                daily_value(
                                    daily.get("precipitationProbability"), index
                                )
                            ),
                        )
                    )
                for part, sun_key, temperature in (
                    ("from", "from", high),
                    ("to", "to", low),
                ):
                    period_time = optional_time(sun.get(sun_key))
                    if temperature is None or period_time is None:
                        continue
                    code = daily_value(daily.get("weather"), index, part)
                    daytime = part == "from"
                    period_condition = CONDITIONS.get(str(code))
                    if not daytime and period_condition == "sunny":
                        period_condition = "clear-night"
                    twice_daily.append(
                        ForecastData(
                            period_time,
                            temperature,
                            None,
                            period_condition,
                            daily_wind(daily, index, part, "speed"),
                            daily_wind(daily, index, part, "direction"),
                            is_daytime=daytime,
                        )
                    )
        hourly = block(payload.get("forecastHourly"))
        hours: list[ForecastData] = []
        temperatures = block(hourly.get("temperature"))
        if (
            temperatures.get("unit") == "℃"
            and series_items(temperatures)
            and (start := optional_time(temperatures.get("pubTime"))) is not None
        ):
            winds = hourly_winds(hourly)
            weather = block(hourly.get("weather"))
            codes = (
                series_items(weather)
                if weather.get("pubTime") == temperatures["pubTime"]
                else []
            )
            for index, value in enumerate(series_items(temperatures)):
                high = number(value)
                if high is None:
                    continue
                date = start + timedelta(hours=index)
                code = codes[index] if index < len(codes) else None
                wind_item = winds.get(date, {})
                # weathercn's legacy hourly speed uses km/h without a unit field.
                wind_unit = block(hourly.get("wind")).get("unit", "km/h")
                hours.append(
                    ForecastData(
                        date,
                        high,
                        None,
                        condition(code, date, suns),
                        number(wind_item.get("speed")) if wind_unit == "km/h" else None,
                        number(wind_item.get("direction")),
                    )
                )
        wind = block(current.get("wind"))
        return WeatherData(
            temperature=temp,
            condition=condition(current.get("weather"), now, suns),
            humidity=measurement(current.get("humidity", {}), "%"),
            pressure=measurement(current.get("pressure", {}), "hPa"),
            wind_speed=measurement(wind.get("speed", {}), "km/h"),
            wind_bearing=measurement(wind.get("direction", {}), "°"),
            apparent_temperature=measurement(current.get("feelsLike", {}), "℃"),
            uv_index=number(current.get("uvIndex")),
            daily=tuple(days),
            hourly=tuple(hours),
            visibility=measurement(block(current.get("visibility")), "km"),
            twice_daily=tuple(twice_daily),
        )
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as err:
        raise XiaomiWeatherError("Invalid weather response") from err


def measurement(value: object, unit: str) -> float | None:
    """Never label a measurement with an unverified unit."""
    if not isinstance(value, dict) or value.get("unit") != unit:
        return None
    return number(value.get("value"))


class XiaomiWeatherClient:
    """Fetch weather using the caller-owned HTTP session."""

    def __init__(
        self, session: ClientSession, city_id: str, latitude: float, longitude: float
    ) -> None:
        """Store location and session without performing I/O."""
        self._session = session
        self._params = {
            "locationKey": f"weathercn:{city_id}",
            "latitude": str(latitude),
            "longitude": str(longitude),
            "days": "15",
            "appKey": "weather20151024",
            "sign": "zUFJoAR2ZVrDy1vF3D07",
            "isGlobal": "false",
            "locale": "zh_cn",
        }

    async def async_get_weather(self) -> WeatherData:
        """Fetch one snapshot with bounded network time and no internal retries."""
        payload = await _async_get_json(self._session, URL, self._params)
        return parse_weather(payload)


@dataclass(frozen=True, slots=True)
class Location:
    """A mainland China weather location returned by Xiaomi."""

    city_id: str
    name: str
    affiliation: str


class XiaomiLocationClient:
    """Resolve coordinates to weather cities during configuration only."""

    def __init__(self, session: ClientSession) -> None:
        """Reuse the caller-owned session."""
        self._session = session

    async def async_locate(self, latitude: float, longitude: float) -> list[Location]:
        """Resolve coordinates to the provider's city identifiers."""
        payload = await _async_get_json(
            self._session,
            f"{LOCATION_URL}/geo",
            {
                "latitude": str(latitude),
                "longitude": str(longitude),
                "locale": "zh_cn",
            },
        )
        try:
            if not isinstance(payload, list):
                raise XiaomiWeatherError("Expected a location list")
            locations: dict[str, Location] = {}
            for item in payload:
                if item.get("status", 0) != 0:
                    continue
                key = item["locationKey"]
                if not key.startswith("weathercn:"):
                    continue
                city_id = key.removeprefix("weathercn:")
                if (
                    re.fullmatch(r"101[0-9]{6}", city_id) is None
                    or not isinstance(item["name"], str)
                    or not item["name"].strip()
                    or not isinstance(item.get("affiliation", ""), str)
                ):
                    raise XiaomiWeatherError("Invalid location metadata")
                locations[city_id] = Location(
                    city_id,
                    item["name"],
                    item.get("affiliation", ""),
                )
            return list(locations.values())
        except (KeyError, TypeError, ValueError, AttributeError) as err:
            raise XiaomiWeatherError("Invalid location response") from err


async def _async_get_json(
    session: ClientSession, url: str, params: dict[str, str]
) -> Any:
    """Bound every provider request and normalize transport failures."""
    try:
        async with session.get(
            url, params=params, timeout=ClientTimeout(total=20)
        ) as response:
            response.raise_for_status()
            return await response.json()
    except (ClientError, TimeoutError, ValueError) as err:
        raise XiaomiWeatherError("Unable to fetch Xiaomi data") from err

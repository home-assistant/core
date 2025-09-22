"""Data models for Meteo.lt integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class Coordinates:
    """Coordinates model."""

    latitude: float
    longitude: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Coordinates:
        """Create coordinates from dict."""
        return cls(
            latitude=data["latitude"],
            longitude=data["longitude"],
        )


@dataclass
class Place:
    """Place model."""

    code: str
    name: str
    administrative_division: str
    country: str | None
    country_code: str
    coordinates: Coordinates

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Place:
        """Create place from dict."""
        return cls(
            code=data["code"],
            name=data["name"],
            administrative_division=data["administrativeDivision"],
            country=data.get("country"),  # Not always present in places list
            country_code=data["countryCode"],
            coordinates=Coordinates.from_dict(data["coordinates"]),
        )


@dataclass
class ForecastTimestamp:
    """Individual forecast timestamp data."""

    forecast_time_utc: datetime
    air_temperature: float | None  # High temperature for daily forecasts
    air_temperature_low: float | None  # Low temperature for daily forecasts
    feels_like_temperature: float | None
    wind_speed: float | None
    wind_gust: float | None
    wind_direction: int | None
    cloud_cover: int | None
    sea_level_pressure: float | None
    relative_humidity: int | None
    total_precipitation: float | None
    condition_code: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForecastTimestamp:
        """Create forecast timestamp from dict."""

        # Parse as UTC datetime
        dt_str = data["forecastTimeUtc"]
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"

        forecast_time = datetime.fromisoformat(dt_str)
        if forecast_time.tzinfo is None:
            forecast_time = forecast_time.replace(tzinfo=UTC)

        return cls(
            forecast_time_utc=forecast_time,
            air_temperature=data.get("airTemperature"),
            air_temperature_low=None,  # Set by daily forecast aggregation
            feels_like_temperature=data.get("feelsLikeTemperature"),
            wind_speed=data.get("windSpeed"),
            wind_gust=data.get("windGust"),
            wind_direction=data.get("windDirection"),
            cloud_cover=data.get("cloudCover"),
            sea_level_pressure=data.get("seaLevelPressure"),
            relative_humidity=data.get("relativeHumidity"),
            total_precipitation=data.get("totalPrecipitation"),
            condition_code=data.get("conditionCode"),
        )


@dataclass
class Forecast:
    """Weather forecast data."""

    place: Place
    forecast_type: str
    forecast_creation_time_utc: datetime
    forecast_timestamps: list[ForecastTimestamp]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Forecast:
        """Create forecast from dict."""

        # Parse creation time as UTC
        creation_time_str = data["forecastCreationTimeUtc"]
        if creation_time_str.endswith("Z"):
            creation_time_str = creation_time_str[:-1] + "+00:00"

        creation_time = datetime.fromisoformat(creation_time_str)
        if creation_time.tzinfo is None:
            creation_time = creation_time.replace(tzinfo=UTC)

        return cls(
            place=Place.from_dict(data["place"]),
            forecast_type=data["forecastType"],
            forecast_creation_time_utc=creation_time,
            forecast_timestamps=[
                ForecastTimestamp.from_dict(ts) for ts in data["forecastTimestamps"]
            ],
        )

    @property
    def current_forecast(self) -> ForecastTimestamp | None:
        """Get the current forecast (closest to now)."""
        if not self.forecast_timestamps:
            return None

        now = datetime.now(UTC)
        closest_forecast = min(
            self.forecast_timestamps,
            key=lambda ts: abs((ts.forecast_time_utc - now).total_seconds()),
        )
        return closest_forecast

    def get_daily_forecasts(self, days: int = 5) -> list[ForecastTimestamp]:
        """Get daily forecasts for the next N days."""
        from collections import defaultdict

        # Weather condition scoring system (higher = better weather)
        condition_scores = {
            "clear": 2,
            "partly-cloudy": 1,
            "cloudy-with-sunny-intervals": 0,
            "cloudy": -0.5,
            "light-rain": -1,
            "rain": -2,
            "heavy-rain": -3,
            "thunder": -2.5,
            "isolated-thunderstorms": -2,
            "thunderstorms": -3,
            "heavy-rain-with-thunderstorms": -4,
            "light-sleet": -1.5,
            "sleet": -2.5,
            "freezing-rain": -3,
            "hail": -3.5,
            "light-snow": -1,
            "snow": -2,
            "heavy-snow": -3,
            "fog": -0.5,
            "null": 0,
        }

        # Group forecasts by date
        forecasts_by_date = defaultdict(list)
        for timestamp in self.forecast_timestamps:
            date = timestamp.forecast_time_utc.date()
            forecasts_by_date[date].append(timestamp)

        daily_forecasts = []
        for date in sorted(forecasts_by_date.keys())[:days]:
            day_forecasts = forecasts_by_date[date]

            if not day_forecasts:
                continue

            # Find the maximum and minimum temperatures for the day
            valid_temps = [
                ts.air_temperature
                for ts in day_forecasts
                if ts.air_temperature is not None
            ]
            max_temp = max(valid_temps, default=None) if valid_temps else None
            min_temp = min(valid_temps, default=None) if valid_temps else None

            # Calculate average condition score for the day
            valid_conditions = [
                condition_scores.get(ts.condition_code, 0)
                for ts in day_forecasts
                if ts.condition_code is not None
            ]

            if valid_conditions:
                avg_score = sum(valid_conditions) / len(valid_conditions)

                # Find condition closest to the average score
                best_condition = min(
                    [ts for ts in day_forecasts if ts.condition_code is not None],
                    key=lambda ts: abs(
                        condition_scores.get(ts.condition_code, 0) - avg_score
                    ),
                    default=day_forecasts[0],
                )
            else:
                best_condition = day_forecasts[0]

            # Create a representative daily forecast
            daily_forecast = ForecastTimestamp(
                forecast_time_utc=day_forecasts[0].forecast_time_utc.replace(
                    hour=12, minute=0, second=0
                ),
                air_temperature=max_temp,
                air_temperature_low=min_temp,
                feels_like_temperature=best_condition.feels_like_temperature,
                wind_speed=best_condition.wind_speed,
                wind_gust=best_condition.wind_gust,
                wind_direction=best_condition.wind_direction,
                cloud_cover=best_condition.cloud_cover,
                sea_level_pressure=best_condition.sea_level_pressure,
                relative_humidity=best_condition.relative_humidity,
                total_precipitation=sum(
                    ts.total_precipitation
                    for ts in day_forecasts
                    if ts.total_precipitation is not None
                )
                or None,
                condition_code=best_condition.condition_code,
            )

            daily_forecasts.append(daily_forecast)

        return daily_forecasts

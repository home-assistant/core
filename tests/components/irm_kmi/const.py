"""Constants shared by the IRM KMI integration tests."""

from irm_kmi_api import CurrentWeatherData, PollenLevel, PollenName, RadarForecast

WEATHER_ENTITY_ID = "weather.brussels"

ALDER_POLLEN_ENTITY_ID = "sensor.brussels_alder_pollen"
RAINFALL_ENTITY_ID = "sensor.brussels_precipitation_intensity"
TEMPERATURE_ENTITY_ID = "sensor.brussels_temperature"
WIND_DIRECTION_ENTITY_ID = "sensor.brussels_wind_direction"
WIND_GUST_SPEED_ENTITY_ID = "sensor.brussels_wind_gust_speed"

CURRENT_WEATHER = CurrentWeatherData(
    condition="cloudy",
    temperature=7.2,
    wind_speed=25.0,
    wind_gust_speed=50.0,
    wind_bearing=180.0,
    uv_index=0.7,
    pressure=1015.0,
)

POLLEN = {
    PollenName.ALDER: PollenLevel.GREEN,
    PollenName.ASH: PollenLevel.YELLOW,
    PollenName.BIRCH: PollenLevel.ORANGE,
    PollenName.GRASSES: PollenLevel.RED,
    PollenName.HAZEL: PollenLevel.PURPLE,
    PollenName.MUGWORT: PollenLevel.ACTIVE,
    PollenName.OAK: PollenLevel.NONE,
}

RADAR_FORECAST = [
    RadarForecast(
        datetime="2023-12-28T15:10:00+01:00",
        native_precipitation=0.1,
        rain_forecast_max=0.15,
        rain_forecast_min=0.05,
        might_rain=True,
        unit="mm/10min",
    ),
    RadarForecast(
        datetime="2023-12-28T15:20:00+01:00",
        native_precipitation=0.05,
        rain_forecast_max=0.1,
        rain_forecast_min=0.0,
        might_rain=True,
        unit="mm/10min",
    ),
    RadarForecast(
        datetime="2023-12-28T15:30:00+01:00",
        native_precipitation=0.4,
        rain_forecast_max=0.6,
        rain_forecast_min=0.2,
        might_rain=True,
        unit="mm/10min",
    ),
    RadarForecast(
        datetime="2023-12-28T15:40:00+01:00",
        native_precipitation=1.2,
        rain_forecast_max=1.5,
        rain_forecast_min=0.9,
        might_rain=True,
        unit="mm/10min",
    ),
]

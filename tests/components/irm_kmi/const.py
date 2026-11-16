"""Constants shared by the IRM KMI integration tests."""

from irm_kmi_api import CurrentWeatherData

WEATHER_ENTITY_ID = "weather.brussels"

CURRENT_WEATHER = CurrentWeatherData(
    condition="cloudy",
    temperature=7.2,
    wind_speed=25.0,
    wind_gust_speed=50.0,
    wind_bearing=180.0,
    uv_index=0.7,
    pressure=1015.0,
)

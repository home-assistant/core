"""Constants shared by the IRM KMI integration tests."""

from irm_kmi_api import CurrentWeatherData, PollenLevel, PollenName

WEATHER_ENTITY_ID = "weather.brussels"

ALDER_POLLEN_ENTITY_ID = "sensor.brussels_alder_pollen"
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

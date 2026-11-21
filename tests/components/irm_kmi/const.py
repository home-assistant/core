"""Constants shared by the IRM KMI integration tests."""

from datetime import datetime

from irm_kmi_api import (
    CurrentWeatherData,
    PollenLevel,
    PollenName,
    WarningData,
    WarningType,
)

WEATHER_ENTITY_ID = "weather.brussels"

WARNING_ENTITY_ID = "binary_sensor.brussels_warning"

ALDER_POLLEN_ENTITY_ID = "sensor.brussels_alder_pollen"
NEXT_WARNING_ENTITY_ID = "sensor.brussels_next_warning"
TEMPERATURE_ENTITY_ID = "sensor.brussels_temperature"
WIND_DIRECTION_ENTITY_ID = "sensor.brussels_wind_direction"
WIND_GUST_SPEED_ENTITY_ID = "sensor.brussels_wind_gust_speed"

WARNINGS = [
    WarningData(
        slug=WarningType.FOG,
        id=7,
        level=1,
        friendly_name="Fog",
        text="Visibility is locally reduced to less than 200 meters.",
        starts_at=datetime.fromisoformat("2023-12-28T16:00:00+01:00"),
        ends_at=datetime.fromisoformat("2023-12-28T20:00:00+01:00"),
    ),
    WarningData(
        slug=WarningType.ICE_OR_SNOW,
        id=2,
        level=2,
        friendly_name="Ice or snow",
        text="Roads are slippery in the morning.",
        starts_at=datetime.fromisoformat("2023-12-29T06:00:00+01:00"),
        ends_at=datetime.fromisoformat("2023-12-29T12:00:00+01:00"),
    ),
]

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

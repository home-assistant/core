"""Constants shared by the IRM KMI integration tests."""

from datetime import datetime

from irm_kmi_api import AnimationFrameData, CurrentWeatherData, RadarAnimationData

WEATHER_ENTITY_ID = "weather.brussels"
RADAR_ENTITY_ID = "image.brussels_radar"

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

ANIMATION = RadarAnimationData(
    hint="No rain forecasted shortly",
    unit="mm/10min",
    location="https://app.meteo.be/localisation.png?th=d",
    most_recent_image_idx=0,
    sequence=[
        AnimationFrameData(
            time=datetime.fromisoformat(f"2023-12-28T15:{minute}:00+01:00"),
            image=f"https://app.meteo.be/frame.png?rs=1&i={minute}",
            value=0.0,
            position=0.0,
            position_higher=0.0,
            position_lower=0.0,
        )
        for minute in ("20", "30")
    ],
)

"""Constants for the HERE Destination Weather service."""
CONF_APP_ID = "app_id"
CONF_APP_CODE = "app_code"
CONF_LOCATION_NAME = "location_name"
CONF_ZIP_CODE = "zip_code"
CONF_LANGUAGE = "language"
CONF_OFFSET = "offset"

DEFAULT_NAME = "here_weather"

MODE_ASTRONOMY = "forecast_astronomy"
MODE_HOURLY = "forecast_hourly"
MODE_DAILY = "forecast_7days"
MODE_DAILY_SIMPLE = "forecast_7days_simple"
MODE_OBSERVATION = "observation"
CONF_MODES = [
    MODE_ASTRONOMY,
    MODE_HOURLY,
    MODE_DAILY,
    MODE_DAILY_SIMPLE,
    MODE_OBSERVATION,
]
DEFAULT_MODE = MODE_DAILY_SIMPLE

ASTRONOMY_ATTRIBUTES = {
    "sunrise": {"name": "Sunrise", "unit_of_measurement": None},
    "sunset": {"name": "Sunset", "unit_of_measurement": None},
    "moonrise": {"name": "Moonrise", "unit_of_measurement": None},
    "moonset": {"name": "Moonset", "unit_of_measurement": None},
    "moonPhase": {"name": "Moon Phase", "unit_of_measurement": "%"},
    "moonPhaseDesc": {"name": "Moon Phase Description", "unit_of_measurement": None},
    "city": {"name": "City", "unit_of_measurement": None},
    "latitude": {"name": "Latitude", "unit_of_measurement": None},
    "longitude": {"name": "Longitude", "unit_of_measurement": None},
    "utcTime": {"name": "Sunrise", "unit_of_measurement": "timestamp"},
}

HOURLY_ATTRIBUTES = {
    "daylight": {"name": "Daylight", "unit_of_measurement": None},
    "description": {"name": "Description", "unit_of_measurement": None},
    "skyInfo": {"name": "Sky Info", "unit_of_measurement": None},
    "skyDescription": {"name": "Sky Description", "unit_of_measurement": None},
    "temperature": {"name": "Temperature", "unit_of_measurement": "°C"},
    "temperatureDesc": {"name": "Temperature Description", "unit_of_measurement": None},
    "comfort": {"name": "Comfort", "unit_of_measurement": "°C"},
    "humidity": {"name": "Humidity", "unit_of_measurement": "%"},
    "dewPoint": {"name": "Dew Point", "unit_of_measurement": "°C"},
    "precipitationProbability": {
        "name": "Precipitation Probability",
        "unit_of_measurement": "%",
    },
    "precipitationDesc": {
        "name": "Precipitation Description",
        "unit_of_measurement": None,
    },
    "rainFall": {"name": "Rain Fall", "unit_of_measurement": "cm"},
    "snowFall": {"name": "Snow Fall", "unit_of_measurement": "cm"},
    "airInfo": {"name": "Air Info", "unit_of_measurement": None},
    "airDescription": {"name": "Air Description", "unit_of_measurement": None},
    "windSpeed": {"name": "Wind Speed", "unit_of_measurement": "km/h"},
    "windDirection": {"name": "Wind Direction", "unit_of_measurement": "°"},
    "windDesc": {"name": "Wind Description", "unit_of_measurement": "cm"},
    "windDescShort": {"name": "Wind Description Short", "unit_of_measurement": "cm"},
    "visibility": {"name": "Visibility", "unit_of_measurement": "km"},
    "icon": {"name": "Icon", "unit_of_measurement": None},
    "iconName": {"name": "Icon Name", "unit_of_measurement": None},
    "iconLink": {"name": "Icon Link", "unit_of_measurement": None},
    "dayOfWeek": {"name": "Day of Week", "unit_of_measurement": None},
    "weekday": {"name": "Week Day", "unit_of_measurement": None},
    "utcTime": {"name": "UTC Time", "unit_of_measurement": "timestamp"},
    "localTime": {"name": "Local Time", "unit_of_measurement": None},
    "localTimeFormat": {"name": "Local Time Format", "unit_of_measurement": None},
}

DAILY_SIMPLE_ATTRIBUTES = {
    "daylight": {"name": "Daylight", "unit_of_measurement": None},
    "description": {"name": "Description", "unit_of_measurement": None},
    "skyInfo": {"name": "Sky Info", "unit_of_measurement": None},
    "skyDescription": {"name": "Sky Description", "unit_of_measurement": None},
    "temperatureDesc": {"name": "Temperature Description", "unit_of_measurement": None},
    "comfort": {"name": "Comfort", "unit_of_measurement": "°C"},
    "highTemperature": {"name": "High Temperature", "unit_of_measurement": "°C"},
    "lowTemperature": {"name": "Low Temperature", "unit_of_measurement": "°C"},
    "humidity": {"name": "Humidity", "unit_of_measurement": "%"},
    "dewPoint": {"name": "Dew Point", "unit_of_measurement": "°C"},
    "precipitationProbability": {
        "name": "Precipitation Probability",
        "unit_of_measurement": "%",
    },
    "precipitationDesc": {
        "name": "Precipitation Description",
        "unit_of_measurement": None,
    },
    "rainFall": {"name": "Rain Fall", "unit_of_measurement": "cm"},
    "snowFall": {"name": "Snow Fall", "unit_of_measurement": "cm"},
    "airInfo": {"name": "Air Info", "unit_of_measurement": None},
    "airDescription": {"name": "Air Description", "unit_of_measurement": None},
    "windSpeed": {"name": "Wind Speed", "unit_of_measurement": "km/h"},
    "windDirection": {"name": "Wind Direction", "unit_of_measurement": "°"},
    "windDesc": {"name": "Wind Description", "unit_of_measurement": "cm"},
    "windDescShort": {"name": "Wind Description Short", "unit_of_measurement": "cm"},
    "beaufortScale": {"name": "Beaufort Scale", "unit_of_measurement": None},
    "beaufortDescription": {
        "name": "Beaufort Scale Description",
        "unit_of_measurement": None,
    },
    "uvIndex": {"name": "UV Index", "unit_of_measurement": None},
    "uvDesc": {"name": "UV Index Description", "unit_of_measurement": None},
    "barometerPressure": {"name": "Barometric Pressure", "unit_of_measurement": "mbar"},
    "icon": {"name": "Icon", "unit_of_measurement": None},
    "iconName": {"name": "Icon Name", "unit_of_measurement": None},
    "iconLink": {"name": "Icon Link", "unit_of_measurement": None},
    "dayOfWeek": {"name": "Day of Week", "unit_of_measurement": None},
    "weekday": {"name": "Week Day", "unit_of_measurement": None},
    "utcTime": {"name": "UTC Time", "unit_of_measurement": "timestamp"},
}

DAILY_ATTRIBUTES = {
    "daylight": {"name": "Daylight", "unit_of_measurement": None},
    "daySegment": {"name": "Day Segment", "unit_of_measurement": None},
    "description": {"name": "Description", "unit_of_measurement": None},
    "skyInfo": {"name": "Sky Info", "unit_of_measurement": None},
    "skyDescription": {"name": "Sky Description", "unit_of_measurement": None},
    "temperature": {"name": "Temperature", "unit_of_measurement": "°C"},
    "temperatureDesc": {"name": "Temperature Description", "unit_of_measurement": None},
    "comfort": {"name": "Comfort", "unit_of_measurement": "°C"},
    "humidity": {"name": "Humidity", "unit_of_measurement": "%"},
    "dewPoint": {"name": "Dew Point", "unit_of_measurement": "°C"},
    "precipitationProbability": {
        "name": "Precipitation Probability",
        "unit_of_measurement": "%",
    },
    "precipitationDesc": {
        "name": "Precipitation Description",
        "unit_of_measurement": None,
    },
    "rainFall": {"name": "Rain Fall", "unit_of_measurement": "cm"},
    "snowFall": {"name": "Snow Fall", "unit_of_measurement": "cm"},
    "airInfo": {"name": "Air Info", "unit_of_measurement": None},
    "airDescription": {"name": "Air Description", "unit_of_measurement": None},
    "windSpeed": {"name": "Wind Speed", "unit_of_measurement": "km/h"},
    "windDirection": {"name": "Wind Direction", "unit_of_measurement": "°"},
    "windDesc": {"name": "Wind Description", "unit_of_measurement": "cm"},
    "windDescShort": {"name": "Wind Description Short", "unit_of_measurement": "cm"},
    "beaufortScale": {"name": "Beaufort Scale", "unit_of_measurement": None},
    "beaufortDescription": {
        "name": "Beaufort Scale Description",
        "unit_of_measurement": None,
    },
    "visibility": {"name": "Visibility", "unit_of_measurement": "km"},
    "icon": {"name": "Icon", "unit_of_measurement": None},
    "iconName": {"name": "Icon Name", "unit_of_measurement": None},
    "iconLink": {"name": "Icon Link", "unit_of_measurement": None},
    "dayOfWeek": {"name": "Day of Week", "unit_of_measurement": None},
    "weekday": {"name": "Week Day", "unit_of_measurement": None},
    "utcTime": {"name": "UTC Time", "unit_of_measurement": "timestamp"},
}

OBSERVATION_ATTRIBUTES = {
    "daylight": {"name": "Daylight", "unit_of_measurement": None},
    "description": {"name": "Description", "unit_of_measurement": None},
    "skyInfo": {"name": "Sky Info", "unit_of_measurement": None},
    "skyDescription": {"name": "Sky Description", "unit_of_measurement": None},
    "temperature": {"name": "Temperature", "unit_of_measurement": "°C"},
    "temperatureDesc": {"name": "Temperature Description", "unit_of_measurement": None},
    "comfort": {"name": "Comfort", "unit_of_measurement": "°C"},
    "highTemperature": {"name": "High Temperature", "unit_of_measurement": "°C"},
    "lowTemperature": {"name": "Low Temperature", "unit_of_measurement": "°C"},
    "humidity": {"name": "Humidity", "unit_of_measurement": "%"},
    "dewPoint": {"name": "Dew Point", "unit_of_measurement": "°C"},
    "precipitation1H": {
        "name": "Precipitation Over 1 Hour",
        "unit_of_measurement": "cm",
    },
    "precipitation3H": {
        "name": "Precipitation Over 3 Hours",
        "unit_of_measurement": "cm",
    },
    "precipitation6H": {
        "name": "Precipitation Over 6 Hours",
        "unit_of_measurement": "cm",
    },
    "precipitation12H": {
        "name": "Precipitation Over 12 Hours",
        "unit_of_measurement": "cm",
    },
    "precipitation24H": {
        "name": "Precipitation Over 24 Hours",
        "unit_of_measurement": "cm",
    },
    "precipitationDesc": {
        "name": "Precipitation Description",
        "unit_of_measurement": None,
    },
    "airInfo": {"name": "Air Info", "unit_of_measurement": None},
    "airDescription": {"name": "Air Description", "unit_of_measurement": None},
    "windSpeed": {"name": "Wind Speed", "unit_of_measurement": "km/h"},
    "windDirection": {"name": "Wind Direction", "unit_of_measurement": "°"},
    "windDesc": {"name": "Wind Description", "unit_of_measurement": "cm"},
    "windDescShort": {"name": "Wind Description Short", "unit_of_measurement": "cm"},
    "barometerPressure": {"name": "Barometric Pressure", "unit_of_measurement": "mbar"},
    "barometerTrend": {
        "name": "Barometric Pressure Trend",
        "unit_of_measurement": None,
    },
    "visibility": {"name": "Visibility", "unit_of_measurement": "km"},
    "snowCover": {"name": "Snow Cover", "unit_of_measurement": "cm"},
    "icon": {"name": "Icon", "unit_of_measurement": None},
    "iconName": {"name": "Icon Name", "unit_of_measurement": None},
    "iconLink": {"name": "Icon Link", "unit_of_measurement": None},
    "ageMinutes": {"name": "Age In Minutes", "unit_of_measurement": "min"},
    "activeAlerts": {"name": "Active Alerts", "unit_of_measurement": None},
    "country": {"name": "Country", "unit_of_measurement": None},
    "state": {"name": "State", "unit_of_measurement": None},
    "city": {"name": "City", "unit_of_measurement": None},
    "latitude": {"name": "Latitude", "unit_of_measurement": None},
    "longitude": {"name": "Longitude", "unit_of_measurement": None},
    "distance": {"name": "Distance", "unit_of_measurement": "km"},
    "elevation": {"name": "Elevation", "unit_of_measurement": "km"},
    "utcTime": {"name": "UTC Time", "unit_of_measurement": "timestamp"},
}

SENSOR_TYPES = {
    MODE_ASTRONOMY: ASTRONOMY_ATTRIBUTES,
    MODE_HOURLY: HOURLY_ATTRIBUTES,
    MODE_DAILY_SIMPLE: DAILY_SIMPLE_ATTRIBUTES,
    MODE_DAILY: DAILY_ATTRIBUTES,
    MODE_OBSERVATION: OBSERVATION_ATTRIBUTES,
}

CONDITION_CLASSES = {
    "clear-night": [
        "night_passing_clouds",
        "night_mostly_clear",
        "night_clearing_skies",
        "night_clear",
    ],
    "cloudy": [
        "night_decreasing_cloudiness",
        "night_mostly_cloudy",
        "night_morning_clouds",
        "night_afternoon_clouds",
        "night_high_clouds",
        "night_high_level_clouds",
        "low_clouds",
        "overcast",
        "cloudy",
        "afternoon_clouds",
        "morning_clouds",
        "high_level_clouds",
        "high_clouds",
    ],
    "fog": [
        "night_low_level_haze",
        "night_smoke",
        "night_haze",
        "dense_fog",
        "fog",
        "light_fog",
        "early_fog",
        "early_fog_followed_by_sunny_skies",
        "low_level_haze",
        "smoke",
        "haze",
        "ice_fog",
        "hazy_sunshine",
    ],
    "hail": ["hail"],
    "lightning": [
        "night_tstorms",
        "night_scattered_tstorms",
        "scattered_tstorms",
        "night_a_few_tstorms",
        "night_isolated_tstorms",
        "night_widely_scattered_tstorms",
        "tstorms_early",
        "isolated_tstorms_late",
        "scattered_tstorms_late",
        "widely_scattered_tstorms",
        "isolated_tstorms",
        "a_few_tstorms",
    ],
    "lightning-rainy": [
        "strong_thunderstorms",
        "severe_thunderstorms",
        "thundershowers",
        "thunderstorms",
        "tstorms_late",
        "tstorms",
    ],
    "partlycloudy": [
        "partly_sunny",
        "mostly_cloudy",
        "broken_clouds",
        "more_clouds_than_sun",
        "night_broken_clouds",
        "increasing_cloudiness",
        "night_partly_cloudy",
        "night_scattered_clouds",
        "passing_clounds",
        "more_sun_than_clouds",
        "scattered_clouds",
        "partly_cloudy",
        "a_mixture_of_sun_and_clouds",
        "increasing_cloudiness",
        "decreasing_cloudiness",
        "clearing_skies",
        "breaks_of_sun_late",
    ],
    "pouring": [
        "heavy_rain_late",
        "heavy_rain_early",
        "tons_of_rain",
        "lots_of_rain",
        "heavy_rain",
        "heavy_rain_early",
        "heavy_rain_early",
    ],
    "rainy": [
        "rain_late",
        "showers_late",
        "rain_early",
        "showery",
        "showers_early",
        "numerous_showers",
        "rain",
        "light_rain_late",
        "sprinkles_late",
        "light_rain_early",
        "sprinkles_early",
        "light_rain",
        "sprinkles",
        "drizzle",
        "night_showers",
        "night_sprinkles",
        "night_rain_showers",
        "night_passing_showers",
        "night_light_showers",
        "night_a_few_showers",
        "night_scattered_showers",
        "rain_early",
        "scattered_showers",
        "a_few_showers",
        "light_showers",
        "passing_showers",
        "rain_showers",
        "showers",
    ],
    "snowy": [
        "heavy_snow_late",
        "heavy_snow_early",
        "heavy_snow",
        "snow_late",
        "snow_early",
        "moderate_snow",
        "snow",
        "light_snow_late",
        "snow_showers_late",
        "flurries_late",
        "light_snow_early",
        "flurries_early",
        "light_snow",
        "snow_flurries",
        "sleet",
        "an_icy_mix_changing_to_snow",
        "an_icy_mix_changing_to_rain",
        "rain_changing_to_snow",
        "icy_mix_early",
        "light_icy_mix_late",
        "icy_mix_late",
        "scattered_flurries",
    ],
    "snowy-rainy": [
        "freezing_rain",
        "light_freezing_rain",
        "snow_showers_early",
        "snow_showers",
        "light_snow_showers",
        "snow_rain_mix",
        "light_icy_mix_early",
        "rain_changing_to_an_icy_mix",
        "snow_changing_to_an_icy_mix",
        "snow_changing_to_rain",
        "heavy_mixture_of_precip",
        "light_mixture_of_precip",
        "icy_mix",
        "mixture_of_precip",
    ],
    "sunny": ["sunny", "clear", "mostly_sunny", "mostly_clear"],
    "windy": [],
    "windy-variant": [],
    "exceptional": [
        "blizzard",
        "snowstorm",
        "duststorm",
        "sandstorm",
        "hurricane",
        "tropical_storm",
        "flood",
        "flash_floods",
        "tornado",
    ],
}

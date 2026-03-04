"""Constants for the SMN integration."""

from typing import Final

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
)

DOMAIN: Final = "smn_argentina"

# Default onboarding locations (Buenos Aires)
DEFAULT_HOME_LATITUDE: Final = -34.6037
DEFAULT_HOME_LONGITUDE: Final = -58.3816

# Update intervals
DEFAULT_SCAN_INTERVAL: Final = 3600  # 1 hour in seconds

# Argentina geographical bounds (approximate)
ARGENTINA_MIN_LATITUDE: Final = -55.0
ARGENTINA_MAX_LATITUDE: Final = -22.0
ARGENTINA_MIN_LONGITUDE: Final = -73.0
ARGENTINA_MAX_LONGITUDE: Final = -53.0

# Weather condition ID mappings - SMN ID to HA condition
# Based on SMN's official weather icon reference table
CONDITION_ID_MAP: Final = {
    3: ATTR_CONDITION_SUNNY,  # Despejado (día)
    5: ATTR_CONDITION_CLEAR_NIGHT,  # Despejado (noche)
    13: ATTR_CONDITION_SUNNY,  # Ligeramente nublado (día)
    14: ATTR_CONDITION_CLEAR_NIGHT,  # Ligeramente nublado (noche)
    19: ATTR_CONDITION_SUNNY,  # Algo nublado (día)
    20: ATTR_CONDITION_CLEAR_NIGHT,  # Algo nublado (noche)
    25: ATTR_CONDITION_PARTLYCLOUDY,  # Parcialmente nublado (día)
    26: ATTR_CONDITION_PARTLYCLOUDY,  # Parcialmente nublado (noche)
    37: ATTR_CONDITION_CLOUDY,  # Mayormente nublado (día)
    38: ATTR_CONDITION_CLOUDY,  # Mayormente nublado (noche)
    43: ATTR_CONDITION_CLOUDY,  # Nublado
    51: ATTR_CONDITION_WINDY,  # Ventoso
    61: ATTR_CONDITION_FOG,  # Neblina
    67: ATTR_CONDITION_FOG,  # Niebla
    69: ATTR_CONDITION_FOG,  # Niebla helada
    71: ATTR_CONDITION_RAINY,  # Llovizna
    72: ATTR_CONDITION_RAINY,  # Lluvias aisladas
    73: ATTR_CONDITION_RAINY,  # Lluvias
    74: ATTR_CONDITION_POURING,  # Chaparrones (día)
    75: ATTR_CONDITION_POURING,  # Chaparrones (noche)
    76: ATTR_CONDITION_LIGHTNING_RAINY,  # Tormentas aisladas
    77: ATTR_CONDITION_SNOWY_RAINY,  # Lluvias y Nevadas
    79: ATTR_CONDITION_SNOWY,  # Nevadas
    81: ATTR_CONDITION_LIGHTNING_RAINY,  # Tormentas
    83: ATTR_CONDITION_POURING,  # Lluvias fuertes
    85: ATTR_CONDITION_SNOWY,  # Nevadas fuertes
    89: ATTR_CONDITION_LIGHTNING_RAINY,  # Tormentas fuertes
    92: ATTR_CONDITION_SNOWY,  # Ventisca alta
    94: ATTR_CONDITION_SNOWY,  # Ventisca
    96: ATTR_CONDITION_SNOWY,  # Ventisca baja
}

# Weather condition text mappings - SMN text to HA condition (fallback)
CONDITIONS_MAP: Final = {
    ATTR_CONDITION_CLEAR_NIGHT: ["despejado noche", "clear night"],
    ATTR_CONDITION_CLOUDY: [
        "nublado",
        "cubierto",
        "cloudy",
        "overcast",
        "mayormente nublado",
    ],
    ATTR_CONDITION_FOG: ["niebla", "fog", "neblina"],
    ATTR_CONDITION_PARTLYCLOUDY: [
        "parcialmente nublado",
        "partly cloudy",
        "algo nublado",
        "ligeramente nublado",
    ],
    ATTR_CONDITION_RAINY: [
        "lluvia",
        "llovizna",
        "rain",
        "drizzle",
        "lluvias aisladas",
    ],
    ATTR_CONDITION_POURING: ["chaparron", "lluvias fuertes"],
    ATTR_CONDITION_LIGHTNING_RAINY: ["tormenta"],
    ATTR_CONDITION_SNOWY: ["nieve", "snow", "nevada", "ventisca"],
    ATTR_CONDITION_SNOWY_RAINY: ["lluvias y nevadas"],
    ATTR_CONDITION_WINDY: ["ventoso"],
    ATTR_CONDITION_SUNNY: ["despejado", "soleado", "clear", "sunny"],
}

# Forecast attribute mappings
FORECAST_MAP: Final = {
    ATTR_FORECAST_CONDITION: "condition",
    ATTR_FORECAST_NATIVE_PRECIPITATION: "precipitation",
    ATTR_FORECAST_NATIVE_TEMP: "temperature",
    ATTR_FORECAST_NATIVE_TEMP_LOW: "templow",
    ATTR_FORECAST_NATIVE_WIND_SPEED: "wind_speed",
    ATTR_FORECAST_TIME: "datetime",
}

# Current weather attribute mappings (from weather endpoint)
ATTR_MAP: Final = {
    "temp": "temp",
    "st": "st",  # Sensación térmica (feels like)
    "humidity": "humidity",
    "pressure": "pressure",
    "wind_speed": "wind_speed",
    "wind_deg": "wind_deg",
    "visibility": "visibility",
    "weather": "weather",
    "description": "description",
}

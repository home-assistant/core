"""Constants for the WeConnect integration."""

from datetime import timedelta

from weconnect.elements.range_status import RangeStatus

DOMAIN = "weconnect"

UPDATE_INTERVAL = timedelta(minutes=5)

BRAND_UNKNOWN = "Unknown"
BRAND_MAPPING = {
    "V": "Volkswagen",
    "N": "Volkswagen",
}

CONF_SPIN = "spin"

FUEL_ENGINES = [
    RangeStatus.Engine.EngineType.GASOLINE,
    RangeStatus.Engine.EngineType.PETROL,
    RangeStatus.Engine.EngineType.DIESEL,
    RangeStatus.Engine.EngineType.CNG,
    RangeStatus.Engine.EngineType.LPG,
]

ELECTRIC_ENGINE = RangeStatus.Engine.EngineType.ELECTRIC

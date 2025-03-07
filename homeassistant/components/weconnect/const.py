"""Constants for the WeConnect integration."""

from datetime import timedelta

from weconnect.elements.range_status import RangeStatus
from weconnect.elements.vehicle import Vehicle

DOMAIN = "weconnect"

UPDATE_INTERVAL = timedelta(minutes=5)

BRAND_UNKNOWN = "Unknown"
BRAND_MAPPING = {
    Vehicle.BrandCode.V: "Volkswagen",
    Vehicle.BrandCode.N: "Volkswagen",
}

CONF_ACCEPT_TERMS = "accept_terms"
CONF_SPIN = "spin"

FUEL_ENGINES = [
    RangeStatus.Engine.EngineType.GASOLINE,
    RangeStatus.Engine.EngineType.PETROL,
    RangeStatus.Engine.EngineType.DIESEL,
    RangeStatus.Engine.EngineType.CNG,
    RangeStatus.Engine.EngineType.LPG,
]

ELECTRIC_ENGINE = RangeStatus.Engine.EngineType.ELECTRIC

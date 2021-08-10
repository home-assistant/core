"""Tests for the CO2 Signal integration."""

VALID_PAYLOAD = {
    "status": "ok",
    "countryCode": "FR",
    "data": {
        "carbonIntensity": 45.98623190095805,
        "fossilFuelPercentage": 5.461182741937103,
    },
    "units": {"carbonIntensity": "gCO2eq/kWh"},
}

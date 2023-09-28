"""Constants for pegel_online tests."""

from aiopegelonline.models import Station, StationMeasurements

from homeassistant.components.pegel_online.const import CONF_STATION

MOCK_STATION_DETAILS_MEISSEN = Station(
    {
        "uuid": "85d686f1-xxxx-xxxx-xxxx-3207b50901a7",
        "number": "501060",
        "shortname": "MEISSEN",
        "longname": "MEISSEN",
        "km": 82.2,
        "agency": "STANDORT DRESDEN",
        "longitude": 13.475467710324812,
        "latitude": 51.16440557554545,
        "water": {"shortname": "ELBE", "longname": "ELBE"},
    }
)

MOCK_STATION_DETAILS_DRESDEN = Station(
    {
        "uuid": "70272185-xxxx-xxxx-xxxx-43bea330dcae",
        "number": "501060",
        "shortname": "DRESDEN",
        "longname": "DRESDEN",
        "km": 55.63,
        "agency": "STANDORT DRESDEN",
        "longitude": 13.738831783620384,
        "latitude": 51.054459765598125,
        "water": {"shortname": "ELBE", "longname": "ELBE"},
    }
)
MOCK_CONFIG_ENTRY_DATA_DRESDEN = {CONF_STATION: "70272185-xxxx-xxxx-xxxx-43bea330dcae"}
MOCK_STATION_MEASUREMENT_DRESDEN = StationMeasurements(
    [
        {
            "shortname": "W",
            "longname": "WASSERSTAND ROHDATEN",
            "unit": "cm",
            "equidistance": 15,
            "currentMeasurement": {
                "timestamp": "2023-07-26T21:15:00+02:00",
                "value": 62,
                "stateMnwMhw": "low",
                "stateNswHsw": "normal",
            },
            "gaugeZero": {
                "unit": "m. ü. NHN",
                "value": 102.7,
                "validFrom": "2019-11-01",
            },
        },
        {
            "shortname": "Q",
            "longname": "ABFLUSS_ROHDATEN",
            "unit": "m³/s",
            "equidistance": 15,
            "currentMeasurement": {
                "timestamp": "2023-07-26T06:00:00+02:00",
                "value": 88.4,
            },
        },
    ]
)

MOCK_STATION_DETAILS_HANAU_BRIDGE = Station(
    {
        "uuid": "07374faf-xxxx-xxxx-xxxx-adc0e0784c4b",
        "number": "24700347",
        "shortname": "HANAU BRÜCKE DFH",
        "longname": "HANAU BRÜCKE DFH",
        "km": 56.398,
        "agency": "ASCHAFFENBURG",
        "water": {"shortname": "MAIN", "longname": "MAIN"},
    }
)
MOCK_CONFIG_ENTRY_DATA_HANAU_BRIDGE = {
    CONF_STATION: "07374faf-xxxx-xxxx-xxxx-adc0e0784c4b"
}
MOCK_STATION_MEASUREMENT_HANAU_BRIDGE = StationMeasurements(
    [
        {
            "shortname": "DFH",
            "longname": "DURCHFAHRTSHÖHE",
            "unit": "cm",
            "equidistance": 15,
            "currentMeasurement": {
                "timestamp": "2023-07-26T19:45:00+02:00",
                "value": 715,
            },
            "gaugeZero": {
                "unit": "m. ü. NHN",
                "value": 106.501,
                "validFrom": "2019-11-01",
            },
        }
    ]
)


MOCK_STATION_DETAILS_WUERZBURG = Station(
    {
        "uuid": "915d76e1-xxxx-xxxx-xxxx-4d144cd771cc",
        "number": "24300600",
        "shortname": "WÜRZBURG",
        "longname": "WÜRZBURG",
        "km": 251.97,
        "agency": "SCHWEINFURT",
        "longitude": 9.925968763247354,
        "latitude": 49.79620901036012,
        "water": {"shortname": "MAIN", "longname": "MAIN"},
    }
)
MOCK_CONFIG_ENTRY_DATA_WUERZBURG = {
    CONF_STATION: "915d76e1-xxxx-xxxx-xxxx-4d144cd771cc"
}
MOCK_STATION_MEASUREMENT_WUERZBURG = StationMeasurements(
    [
        {
            "shortname": "W",
            "longname": "WASSERSTAND ROHDATEN",
            "unit": "cm",
            "equidistance": 15,
            "currentMeasurement": {
                "timestamp": "2023-07-26T19:15:00+02:00",
                "value": 159,
                "stateMnwMhw": "normal",
                "stateNswHsw": "normal",
            },
            "gaugeZero": {
                "unit": "m. ü. NHN",
                "value": 164.511,
                "validFrom": "2019-11-01",
            },
        },
        {
            "shortname": "LT",
            "longname": "LUFTTEMPERATUR",
            "unit": "°C",
            "equidistance": 60,
            "currentMeasurement": {
                "timestamp": "2023-07-26T19:00:00+02:00",
                "value": 21.2,
            },
        },
        {
            "shortname": "WT",
            "longname": "WASSERTEMPERATUR",
            "unit": "°C",
            "equidistance": 60,
            "currentMeasurement": {
                "timestamp": "2023-07-26T19:00:00+02:00",
                "value": 22.1,
            },
        },
        {
            "shortname": "VA",
            "longname": "FLIESSGESCHWINDIGKEIT",
            "unit": "m/s",
            "equidistance": 15,
            "currentMeasurement": {
                "timestamp": "2023-07-26T19:15:00+02:00",
                "value": 0.58,
            },
        },
        {
            "shortname": "O2",
            "longname": "SAUERSTOFFGEHALT",
            "unit": "mg/l",
            "equidistance": 60,
            "currentMeasurement": {
                "timestamp": "2023-07-26T19:00:00+02:00",
                "value": 8.4,
            },
        },
        {
            "shortname": "PH",
            "longname": "PH-WERT",
            "unit": "--",
            "equidistance": 60,
            "currentMeasurement": {
                "timestamp": "2023-07-26T19:00:00+02:00",
                "value": 8.1,
            },
        },
        {
            "shortname": "Q",
            "longname": "ABFLUSS",
            "unit": "m³/s",
            "equidistance": 15,
            "currentMeasurement": {
                "timestamp": "2023-07-26T19:00:00+02:00",
                "value": 102,
            },
        },
    ]
)

MOCK_NEARBY_STATIONS = {
    "70272185-xxxx-xxxx-xxxx-43bea330dcae": MOCK_STATION_DETAILS_DRESDEN,
    "85d686f1-xxxx-xxxx-xxxx-3207b50901a7": MOCK_STATION_DETAILS_MEISSEN,
}

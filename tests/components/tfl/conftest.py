"""Common fixtures for the Transport for London tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

MOCK_DATA_SENSOR_ARRIVALS = [
    {
        "line_name": "141",
        "destination_name": "London Bridge",
        "time_to_station": 503,
    },
    {
        "line_name": "29",
        "destination_name": "Trafalgar Square",
        "time_to_station": 505,
    },
    {
        "line_name": "141",
        "destination_name": "London Bridge",
        "time_to_station": 974,
    },
    {
        "line_name": "29",
        "destination_name": "Trafalgar Square",
        "time_to_station": 1441,
    },
]

MOCK_DATA_TFL_STATION_ARRIVALS = [
    {
        "$type": "Tfl.Api.Presentation.Entities.Prediction, Tfl.Api.Presentation.Entities",
        "id": "-230128189",
        "operationType": 1,
        "vehicleId": "LJ62BND",
        "naptanId": "11111111114HB",
        "stationName": "Bob's Road",
        "lineId": "141",
        "lineName": "141",
        "platformName": "HB",
        "direction": "outbound",
        "bearing": "174",
        "destinationNaptanId": "",
        "destinationName": "London Bridge",
        "timestamp": "2023-10-22T07:40:51.5582814Z",
        "timeToStation": 974,
        "currentLocation": "",
        "towards": "Finsbury Park Or Newington Green",
        "expectedArrival": "2023-10-22T07:57:05Z",
        "timeToLive": "2023-10-22T07:57:35Z",
        "modeName": "bus",
        "timing": {
            "$type": "Tfl.Api.Presentation.Entities.PredictionTiming, Tfl.Api.Presentation.Entities",
            "countdownServerAdjustment": "-00:00:04.2891455",
            "source": "2023-10-20T14:40:30.76Z",
            "insert": "2023-10-22T07:40:09.716Z",
            "read": "2023-10-22T07:40:05.396Z",
            "sent": "2023-10-22T07:40:51Z",
            "received": "0001-01-01T00:00:00Z",
        },
    },
    {
        "$type": "Tfl.Api.Presentation.Entities.Prediction, Tfl.Api.Presentation.Entities",
        "id": "1869737350",
        "operationType": 1,
        "vehicleId": "LK66GDZ",
        "naptanId": "11111111114HB",
        "stationName": "Bob's Road",
        "lineId": "141",
        "lineName": "141",
        "platformName": "HB",
        "direction": "outbound",
        "bearing": "174",
        "destinationNaptanId": "",
        "destinationName": "London Bridge",
        "timestamp": "2023-10-22T07:40:51.5582814Z",
        "timeToStation": 503,
        "currentLocation": "",
        "towards": "Finsbury Park Or Newington Green",
        "expectedArrival": "2023-10-22T07:49:14Z",
        "timeToLive": "2023-10-22T07:49:44Z",
        "modeName": "bus",
        "timing": {
            "$type": "Tfl.Api.Presentation.Entities.PredictionTiming, Tfl.Api.Presentation.Entities",
            "countdownServerAdjustment": "-00:00:04.3051722",
            "source": "2023-10-20T14:40:30.76Z",
            "insert": "2023-10-22T07:40:19.73Z",
            "read": "2023-10-22T07:40:15.409Z",
            "sent": "2023-10-22T07:40:51Z",
            "received": "0001-01-01T00:00:00Z",
        },
    },
    {
        "$type": "Tfl.Api.Presentation.Entities.Prediction, Tfl.Api.Presentation.Entities",
        "id": "-76664292",
        "operationType": 1,
        "vehicleId": "LJ13FBL",
        "naptanId": "11111111114HB",
        "stationName": "Bob's Road",
        "lineId": "29",
        "lineName": "29",
        "platformName": "HB",
        "direction": "outbound",
        "bearing": "174",
        "destinationNaptanId": "",
        "destinationName": "Trafalgar Square",
        "timestamp": "2023-10-22T07:40:51.5582814Z",
        "timeToStation": 1441,
        "currentLocation": "",
        "towards": "Finsbury Park Or Newington Green",
        "expectedArrival": "2023-10-22T08:04:52Z",
        "timeToLive": "2023-10-22T08:05:22Z",
        "modeName": "bus",
        "timing": {
            "$type": "Tfl.Api.Presentation.Entities.PredictionTiming, Tfl.Api.Presentation.Entities",
            "countdownServerAdjustment": "-00:00:04.2950995",
            "source": "2023-10-20T14:40:30.76Z",
            "insert": "2023-10-22T07:39:59.696Z",
            "read": "2023-10-22T07:39:55.394Z",
            "sent": "2023-10-22T07:40:51Z",
            "received": "0001-01-01T00:00:00Z",
        },
    },
    {
        "$type": "Tfl.Api.Presentation.Entities.Prediction, Tfl.Api.Presentation.Entities",
        "id": "59517071",
        "operationType": 1,
        "vehicleId": "LJ13FCE",
        "naptanId": "11111111114HB",
        "stationName": "Bob's Road",
        "lineId": "29",
        "lineName": "29",
        "platformName": "HB",
        "direction": "outbound",
        "bearing": "174",
        "destinationNaptanId": "",
        "destinationName": "Trafalgar Square",
        "timestamp": "2023-10-22T07:40:51.5582814Z",
        "timeToStation": 505,
        "currentLocation": "",
        "towards": "Finsbury Park Or Newington Green",
        "expectedArrival": "2023-10-22T07:49:16Z",
        "timeToLive": "2023-10-22T07:49:46Z",
        "modeName": "bus",
        "timing": {
            "$type": "Tfl.Api.Presentation.Entities.PredictionTiming, Tfl.Api.Presentation.Entities",
            "countdownServerAdjustment": "-00:00:04.3205075",
            "source": "2023-10-20T14:40:30.76Z",
            "insert": "2023-10-22T07:40:07.089Z",
            "read": "2023-10-22T07:40:02.8Z",
            "sent": "2023-10-22T07:40:51Z",
            "received": "0001-01-01T00:00:00Z",
        },
    },
]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tfl.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry

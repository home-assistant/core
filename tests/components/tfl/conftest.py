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
MOCK_DATA_TFL_STOP_POINT_INFO = {
    "$type": "Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities",
    "naptanId": "AAAAAAAA1",
    "indicator": "Stop HB",
    "stopLetter": "HB",
    "modes": ["bus"],
    "icsCode": "1006574",
    "smsCode": "55465",
    "stopType": "NaptanPublicBusCoachTram",
    "id": "AAAAAAAA1",
    "commonName": "Endymion Road",
    "placeType": "StopPoint",
    "children": [],
    "lat": 51.57597,
    "lon": -0.09845,
}
MOCK_DATA_TFL_STOP_POINT_INFO_WITH_CHILDREN = {
    "$type": "Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities",
    "naptanId": "910GHRGYGL",
    "modes": ["bus", "overground"],
    "icsCode": "1001139",
    "smsCode": "52931",
    "stopType": "NaptanRailStation",
    "stationNaptan": "910GHRGYGL",
    "id": "910GHRGYGL",
    "commonName": "Harringay Green Lanes Rail Station",
    "placeType": "StopPoint",
    "children": [
        {
            "$type": "Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities",
            "naptanId": "4900HRGYGL1",
            "indicator": "Entrance",
            "modes": ["bus", "overground"],
            "icsCode": "1001139",
            "stopType": "NaptanRailEntrance",
            "stationNaptan": "910GHRGYGL",
            "lines": [],
            "lineGroup": [],
            "lineModeGroups": [],
            "id": "4900HRGYGL1",
            "commonName": "Harringay Green Lanes Station",
            "placeType": "StopPoint",
            "children": [],
            "lat": 51.57702,
            "lon": -0.0988,
        },
        {
            "$type": "Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities",
            "naptanId": "4900HRGYGL2",
            "indicator": "Entrance",
            "modes": ["bus", "overground"],
            "icsCode": "1001139",
            "stopType": "NaptanRailEntrance",
            "stationNaptan": "910GHRGYGL",
            "lines": [],
            "lineGroup": [],
            "lineModeGroups": [],
            "id": "4900HRGYGL2",
            "commonName": "Harringay Green Lanes Station",
            "placeType": "StopPoint",
            "additionalProperties": [],
            "children": [],
            "lat": 51.57718,
            "lon": -0.09879,
        },
        {
            "$type": "Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities",
            "naptanId": "490G000572",
            "modes": ["bus"],
            "icsCode": "1007837",
            "stopType": "NaptanOnstreetBusCoachStopPair",
            "stationNaptan": "490G000572",
            "lines": [
                {
                    "$type": "Tfl.Api.Presentation.Entities.Identifier, Tfl.Api.Presentation.Entities",
                    "id": "w5",
                    "name": "W5",
                    "uri": "/Line/w5",
                    "type": "Line",
                    "crowding": {
                        "$type": "Tfl.Api.Presentation.Entities.Crowding, Tfl.Api.Presentation.Entities"
                    },
                    "routeType": "Unknown",
                    "status": "Unknown",
                }
            ],
            "lineGroup": [
                {
                    "$type": "Tfl.Api.Presentation.Entities.LineGroup, Tfl.Api.Presentation.Entities",
                    "naptanIdReference": "490007837HA",
                    "stationAtcoCode": "490G000572",
                    "lineIdentifier": ["w5"],
                }
            ],
            "lineModeGroups": [
                {
                    "$type": "Tfl.Api.Presentation.Entities.LineModeGroup, Tfl.Api.Presentation.Entities",
                    "modeName": "bus",
                    "lineIdentifier": ["w5"],
                }
            ],
            "id": "490G000572",
            "commonName": "Harringay Sainsbury's",
            "placeType": "StopPoint",
            "additionalProperties": [],
            "children": [
                {
                    "$type": "Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities",
                    "naptanId": "AAAAAAAA1",
                    "indicator": "Stop HA",
                    "stopLetter": "HA",
                    "modes": ["bus"],
                    "icsCode": "1007837",
                    "stopType": "NaptanPublicBusCoachTram",
                    "stationNaptan": "490G000572",
                    "lines": [
                        {
                            "$type": "Tfl.Api.Presentation.Entities.Identifier, Tfl.Api.Presentation.Entities",
                            "id": "w5",
                            "name": "W5",
                            "uri": "/Line/w5",
                            "type": "Line",
                            "crowding": {
                                "$type": "Tfl.Api.Presentation.Entities.Crowding, Tfl.Api.Presentation.Entities"
                            },
                            "routeType": "Unknown",
                            "status": "Unknown",
                        }
                    ],
                    "lineGroup": [
                        {
                            "$type": "Tfl.Api.Presentation.Entities.LineGroup, Tfl.Api.Presentation.Entities",
                            "naptanIdReference": "490007837HA",
                            "stationAtcoCode": "490G000572",
                            "lineIdentifier": ["w5"],
                        }
                    ],
                    "lineModeGroups": [
                        {
                            "$type": "Tfl.Api.Presentation.Entities.LineModeGroup, Tfl.Api.Presentation.Entities",
                            "modeName": "bus",
                            "lineIdentifier": ["w5"],
                        }
                    ],
                    "status": True,
                    "id": "AAAAAAAA1",
                    "commonName": "Harringay Sainsbury's",
                    "placeType": "StopPoint",
                    "children": [],
                    "lat": 51.57609,
                    "lon": -0.09615,
                }
            ],
            "lat": 51.57609,
            "lon": -0.09615,
        },
    ],
    "lat": 51.577182,
    "lon": -0.098144,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tfl.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry

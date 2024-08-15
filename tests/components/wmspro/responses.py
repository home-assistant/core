"""Example JSON responses for the wmspro tests."""

import json


def example_config_test():
    """Return JSON configuration taken from official documentation."""
    return json.loads("""
{
    "command": "getConfiguration",
    "protocolVersion": "1.0.0",
    "destinations": [
        {
            "id": 17776,
            "animationType": 0,
            "names": [
                "Küche",
                "",
                "",
                ""
            ],
            "actions": [
                {
                    "id": 0,
                    "actionType": 0,
                    "actionDescription": 2,
                    "minValue": 0,
                    "maxValue": 100
                },
                {
                    "id": 6,
                    "actionType": 2,
                    "actionDescription": 3,
                    "minValue": -127,
                    "maxValue": 127
                },
                {
                    "id": 16,
                    "actionType": 6,
                    "actionDescription": 12
                },
                {
                    "id": 22,
                    "actionType": 8,
                    "actionDescription": 13
                },
                {
                    "id": 23,
                    "actionType": 7,
                    "actionDescription": 12
                }
            ]
        },
        {
            "id": 200951,
            "animationType": 999,
            "names": [
                "Aktor Potentialfrei",
                "",
                "",
                ""
            ],
            "actions": [
                {
                    "id": 22,
                    "actionType": 8,
                    "actionDescription": 13
                },
                {
                    "id": 26,
                    "actionType": 9,
                    "actionDescription": 999,
                    "minValue": 0,
                    "maxValue": 16
                }
            ]
        }
    ],
    "rooms": [
        {
            "id": 42581,
            "name": "Raum 0",
            "destinations": [
                17776,
                116682,
                194367,
                200951
            ],
            "scenes": [
                688966
            ]
        }
    ],
    "scenes": [
        {
            "id": 688966,
            "names": [
                "Gute Nacht",
                "",
                "",
                ""
            ]
        }
    ]
}
               """)


def example_config_prod():
    """Return JSON configuration taken from production WebControl pro."""
    return json.loads("""
{
    "command": "getConfiguration",
    "protocolVersion": "1.0.0",
    "destinations": [
        {
            "id": 58717,
            "animationType": 1,
            "names": [
                "Markise",
                "",
                "",
                ""
            ],
            "actions": [
                {
                    "id": 0,
                    "actionType": 0,
                    "actionDescription": 0,
                    "minValue": 0,
                    "maxValue": 100
                },
                {
                    "id": 16,
                    "actionType": 6,
                    "actionDescription": 12
                },
                {
                    "id": 22,
                    "actionType": 8,
                    "actionDescription": 13
                }
            ]
        },
        {
            "id": 97358,
            "animationType": 6,
            "names": [
                "Licht",
                "",
                "",
                ""
            ],
            "actions": [
                {
                    "id": 0,
                    "actionType": 0,
                    "actionDescription": 8,
                    "minValue": 0,
                    "maxValue": 100
                },
                {
                    "id": 17,
                    "actionType": 6,
                    "actionDescription": 12
                },
                {
                    "id": 20,
                    "actionType": 4,
                    "actionDescription": 6
                },
                {
                    "id": 22,
                    "actionType": 8,
                    "actionDescription": 13
                }
            ]
        }
    ],
    "rooms": [
        {
            "id": 19239,
            "name": "Terrasse",
            "destinations": [
                58717,
                97358
            ],
            "scenes": [
                687471,
                765095
            ]
        }
    ],
    "scenes": [
        {
            "id": 687471,
            "names": [
                "Licht an",
                "",
                "",
                ""
            ]
        },
        {
            "id": 765095,
            "names": [
                "Licht aus",
                "",
                "",
                ""
            ]
        }
    ]
}
               """)


def example_status_prod_awning():
    """Return JSON awning status taken from production WebControl pro."""
    return json.loads("""
{
    "command": "getStatus",
    "protocolVersion": "1.0.0",
    "details": [
        {
            "destinationId": 58717,
            "data": {
                "drivingCause": 0,
                "heartbeatError": false,
                "blocking": false,
                "productData": [
                    {
                        "actionId": 0,
                        "value": {
                            "percentage": 100
                        }
                    }
                ]
            }
        }
    ]
}
               """)

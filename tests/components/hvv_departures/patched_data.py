"""Patched data for tests."""

PATCHED_DEPARTURE_LIST = {
    "returnCode": "OK",
    "time": {"date": "26.01.2020", "time": "22:52"},
    "departures": [
        {
            "line": {
                "name": "U1",
                "direction": "Großhansdorf",
                "origin": "Norderstedt Mitte",
                "type": {
                    "simpleType": "TRAIN",
                    "shortInfo": "U",
                    "longInfo": "U-Bahn",
                    "model": "DT4",
                },
                "id": "HHA-U:U1_HHA-U",
            },
            "timeOffset": 0,
            "delay": 0,
            "serviceId": 1482563187,
            "station": {"combinedName": "Wartenau", "id": "Master:10901"},
            "attributes": [{"isPlanned": True, "types": ["REALTIME", "ACCURATE"]}],
        },
        {
            "line": {
                "name": "25",
                "direction": "Bf. Altona",
                "origin": "U Burgstraße",
                "type": {
                    "simpleType": "BUS",
                    "shortInfo": "Bus",
                    "longInfo": "Niederflur Metrobus",
                    "model": "Gelenkbus",
                },
                "id": "HHA-B:25_HHA-B",
            },
            "timeOffset": 1,
            "delay": 0,
            "serviceId": 74567,
            "station": {"combinedName": "U Wartenau", "id": "Master:60015"},
            "attributes": [{"isPlanned": True, "types": ["REALTIME", "ACCURATE"]}],
        },
        {
            "line": {
                "name": "25",
                "direction": "U Burgstraße",
                "origin": "Bf. Altona",
                "type": {
                    "simpleType": "BUS",
                    "shortInfo": "Bus",
                    "longInfo": "Niederflur Metrobus",
                    "model": "Gelenkbus",
                },
                "id": "HHA-B:25_HHA-B",
            },
            "timeOffset": 5,
            "delay": 0,
            "serviceId": 74328,
            "station": {"combinedName": "U Wartenau", "id": "Master:60015"},
            "attributes": [{"isPlanned": True, "types": ["REALTIME", "ACCURATE"]}],
        },
        {
            "line": {
                "name": "U1",
                "direction": "Norderstedt Mitte",
                "origin": "Großhansdorf",
                "type": {
                    "simpleType": "TRAIN",
                    "shortInfo": "U",
                    "longInfo": "U-Bahn",
                    "model": "DT4",
                },
                "id": "HHA-U:U1_HHA-U",
            },
            "timeOffset": 8,
            "delay": 0,
            "station": {"combinedName": "Wartenau", "id": "Master:10901"},
            "attributes": [{"isPlanned": True, "types": ["REALTIME", "ACCURATE"]}],
        },
        {
            "line": {
                "name": "U1",
                "direction": "Ohlstedt",
                "origin": "Norderstedt Mitte",
                "type": {
                    "simpleType": "TRAIN",
                    "shortInfo": "U",
                    "longInfo": "U-Bahn",
                    "model": "DT4",
                },
                "id": "HHA-U:U1_HHA-U",
            },
            "timeOffset": 10,
            "delay": 0,
            "station": {"combinedName": "Wartenau", "id": "Master:10901"},
            "attributes": [{"isPlanned": True, "types": ["REALTIME", "ACCURATE"]}],
        },
    ],
    "filter": [
        {
            "serviceID": "HHA-U:U1_HHA-U",
            "stationIDs": ["Master:10902"],
            "label": "Fuhlsbüttel Nord / Ochsenzoll / Norderstedt Mitte / Kellinghusenstraße / Ohlsdorf / Garstedt",
            "serviceName": "U1",
        },
        {
            "serviceID": "HHA-U:U1_HHA-U",
            "stationIDs": ["Master:60904"],
            "label": "Volksdorf / Farmsen / Großhansdorf / Ohlstedt",
            "serviceName": "U1",
        },
        {
            "serviceID": "HHA-B:25_HHA-B",
            "stationIDs": ["Master:10047"],
            "label": "Sachsenstraße / U Burgstraße",
            "serviceName": "25",
        },
        {
            "serviceID": "HHA-B:25_HHA-B",
            "stationIDs": ["Master:60029"],
            "label": "Winterhuder Marktplatz / Bf. Altona",
            "serviceName": "25",
        },
        {
            "serviceID": "HHA-B:36_HHA-B",
            "stationIDs": ["Master:10049"],
            "label": "S Blankenese / Rathausmarkt",
            "serviceName": "36",
        },
        {
            "serviceID": "HHA-B:36_HHA-B",
            "stationIDs": ["Master:60013"],
            "label": "Berner Heerweg",
            "serviceName": "36",
        },
        {
            "serviceID": "HHA-B:606_HHA-B",
            "stationIDs": ["Master:10047"],
            "label": "S Landwehr (Ramazan-Avci-Platz) - Rathausmarkt",
            "serviceName": "606",
        },
        {
            "serviceID": "HHA-B:606_HHA-B",
            "stationIDs": ["Master:60029"],
            "label": "Uferstraße - Winterhuder Marktplatz / Uferstraße - S Hamburg Airport / Uferstraße - U Langenhorn Markt (Krohnstieg)",
            "serviceName": "606",
        },
        {
            "serviceID": "HHA-B:608_HHA-B",
            "stationIDs": ["Master:10048"],
            "label": "Rathausmarkt / S Reeperbahn",
            "serviceName": "608",
        },
        {
            "serviceID": "HHA-B:608_HHA-B",
            "stationIDs": ["Master:60012"],
            "label": "Bf. Rahlstedt (Amtsstraße) / Großlohe",
            "serviceName": "608",
        },
    ],
    "serviceTypes": ["UBAHN", "BUS", "METROBUS", "SCHNELLBUS", "NACHTBUS"],
}

PATCHED_CONFIG_ENTRY_DATA = {
    "host": "api-test.geofox.de",
    "username": "test-username",
    "password": "test-password",
    "station": {
        "city": "Schmalfeld",
        "combinedName": "Schmalfeld, Holstenstra\u00dfe",
        "coordinate": {"x": 9.986115, "y": 53.874122},
        "hasStationInformation": False,
        "id": "Master:75279",
        "name": "Holstenstra\u00dfe",
        "serviceTypes": ["bus"],
        "type": "STATION",
    },
    "stationInformation": {"returnCode": "OK"},
}

PATCHED_CONFIG_ENTRY_OPTIONS = {
    "filter": [
        {
            "label": "S Landwehr (Ramazan-Avci-Platz) - Rathausmarkt",
            "serviceID": "HHA-B:606_HHA-B",
            "serviceName": "606",
            "stationIDs": ["Master:10047"],
        }
    ],
    "offset": 10,
    "realtime": True,
}

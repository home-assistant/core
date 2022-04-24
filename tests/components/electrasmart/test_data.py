"""Test config data from Electra Smart."""

MOCK_DATA_GENERATE_TOKEN_RESP = {
    "id": 99,
    "status": 0,
    "desc": None,
    "data": {"res": 0, "res_desc": None},
}
MOCK_DATA_OTP_RESP = {
    "id": 99,
    "status": 0,
    "desc": None,
    "data": {
        "token": "ec7a0db6c1f148ca8c0f48aabb5f8150",
        "sid": "bd6f11f947244e5d9612eba89e91112b",
        "res": 0,
        "res_desc": None,
    },
}

MOCK_DATA_INVALID_PHONE_NUMBER = {
    "id": 99,
    "status": 0,
    "desc": None,
    "data": {"res": 100, "res_desc": None},
}

MOCK_DATA_INVALID_OTP = {
    "id": 99,
    "status": 1,
    "desc": None,
    "data": {"res": 100, "res_desc": None},
}

MOCK_DATA_GET_DEVICES = {
    "id": 99,
    "status": 0,
    "desc": None,
    "data": {
        "devices": [
            {
                "providerName": None,
                "deviceTypeName": "A/C",
                "manufactor": "Midea",
                "photoId": None,
                "permissions": 15,
                "deviceTypeId": 1,
                "name": "סלון",
                "status": 1,
                "providerid": 1,
                "latitude": None,
                "longitude": None,
                "location": None,
                "sn": "AAAAAAAA",
                "mac": "BBBBBBBB",
                "model": "K071130882",
                "hwVersion": None,
                "fmVersion": None,
                "userId": 100556,
                "manufactorId": 2,
                "iconId": "1",
                "hasImage": False,
                "deviceToken": "9M9HXcY9txnZDf6iby",
                "mqttId": "d:alk2da:midea_ac:502DBB5C59D0",
                "enableEvents": True,
                "isActivated": False,
                "logLevel": None,
                "lastIntervalActivity": None,
                "PowerOnID": None,
                "IsDebugMode": False,
                "regdate": "2021-03-31T21:12:39",
                "id": 93485,
            },
            {
                "providerName": None,
                "deviceTypeName": "A/C",
                "manufactor": "Midea",
                "photoId": None,
                "permissions": 15,
                "deviceTypeId": 1,
                "name": "סלון",
                "status": 1,
                "providerid": 1,
                "latitude": None,
                "longitude": None,
                "location": None,
                "sn": "YYYYYYYY",
                "mac": "XXXXXXXXX",
                "model": "K071130881",
                "hwVersion": None,
                "fmVersion": None,
                "userId": 100556,
                "manufactorId": 2,
                "iconId": "1",
                "hasImage": False,
                "deviceToken": "PfmqcGqfcRFEAPZHfA",
                "mqttId": "d:alk2da:midea_ac:502DBB5D12A5",
                "enableEvents": True,
                "isActivated": False,
                "logLevel": None,
                "lastIntervalActivity": None,
                "PowerOnID": None,
                "IsDebugMode": False,
                "regdate": "2021-03-31T21:07:25",
                "id": 93520,
            },
        ],
        "res": 0,
        "res_desc": None,
    },
}

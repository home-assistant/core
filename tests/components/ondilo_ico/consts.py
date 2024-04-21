"""Define consts used during Ondilo testing."""

POOL1 = {
    "id": 1,
    "name": "Pool 1",
    "type": "outdoor_inground_pool",
    "volume": 100,
    "disinfection": {
        "primary": "chlorine",
        "secondary": {"uv_sanitizer": False, "ozonator": False},
    },
    "address": {
        "street": "1 Rue de Paris",
        "zipcode": "75000",
        "city": "Paris",
        "country": "France",
        "latitude": 48.861783,
        "longitude": 2.337421,
    },
    "updated_at": "2024-01-01T01:00:00+0000",
}

POOL2 = {
    "id": 2,
    "name": "Pool 2",
    "type": "outdoor_inground_pool",
    "volume": 120,
    "disinfection": {
        "primary": "chlorine",
        "secondary": {"uv_sanitizer": False, "ozonator": False},
    },
    "address": {
        "street": "1 Rue de Paris",
        "zipcode": "75000",
        "city": "Paris",
        "country": "France",
        "latitude": 48.861783,
        "longitude": 2.337421,
    },
    "updated_at": "2024-01-01T01:00:00+0000",
}

TWO_POOLS = [POOL1, POOL2]

ICO_DETAILS = {
    "uuid": "111112222233333444445555",
    "serial_number": "W1122333044455",
    "sw_version": "1.7.1-stable",
}

LAST_MEASURES = [
    {
        "data_type": "temperature",
        "value": 19,
        "value_time": "2024-01-01 01:00:00",
        "is_valid": True,
        "exclusion_reason": None,
    },
    {
        "data_type": "ph",
        "value": 9.29,
        "value_time": "2024-01-01 01:00:00",
        "is_valid": True,
        "exclusion_reason": None,
    },
    {
        "data_type": "orp",
        "value": 647,
        "value_time": "2024-01-01 01:00:00",
        "is_valid": True,
        "exclusion_reason": None,
    },
    {
        "data_type": "salt",
        "value": None,
        "value_time": "2024-01-01 01:00:00",
        "is_valid": True,
        "exclusion_reason": None,
    },
    {
        "data_type": "battery",
        "value": 50,
        "value_time": "2024-01-01 01:00:00",
        "is_valid": True,
        "exclusion_reason": None,
    },
    {
        "data_type": "tds",
        "value": 845,
        "value_time": "2024-01-01 01:00:00",
        "is_valid": True,
        "exclusion_reason": None,
    },
    {
        "data_type": "rssi",
        "value": 60,
        "value_time": "2024-01-01 01:00:00",
        "is_valid": True,
        "exclusion_reason": None,
    },
]

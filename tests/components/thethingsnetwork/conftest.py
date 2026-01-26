"""Define fixtures for the The Things Network tests."""

from unittest.mock import AsyncMock, patch

import pytest
from ttn_client import TTNSensorValue

from homeassistant.components.thethingsnetwork.const import (
    CONF_APP_ID,
    DOMAIN,
    TTN_API_HOST,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST

from tests.common import MockConfigEntry

HOST = "example.com"
APP_ID = "my_app"
API_KEY = "my_api_key"

DEVICE_ID = "my_device"
DEVICE_ID_2 = "my_device_2"
DEVICE_FIELD = "a_field"
DEVICE_FIELD_2 = "a_field_2"
DEVICE_FIELD_VALUE = 42

DATA = {
    DEVICE_ID: {
        DEVICE_FIELD: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-11T08:49:11.153738893Z",
            },
            DEVICE_FIELD,
            DEVICE_FIELD_VALUE,
        )
    }
}

DATA_UPDATE = {
    DEVICE_ID: {
        DEVICE_FIELD: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID},
                "received_at": "2024-03-12T08:49:11.153738893Z",
            },
            DEVICE_FIELD,
            DEVICE_FIELD_VALUE,
        )
    },
    DEVICE_ID_2: {
        DEVICE_FIELD_2: TTNSensorValue(
            {
                "end_device_ids": {"device_id": DEVICE_ID_2},
                "received_at": "2024-03-12T08:49:11.153738893Z",
            },
            DEVICE_FIELD_2,
            DEVICE_FIELD_VALUE,
        )
    },
}

# Device tracker test data
TRACKER_DEVICE_ID = "t1000_tracker"

# Wi-Fi scan data (measurementId 5001)
WIFI_SCAN_DATA = [
    {"mac": "AA:BB:CC:DD:EE:01", "rssi": -45},
    {"mac": "AA:BB:CC:DD:EE:02", "rssi": -67},
    {"mac": "AA:BB:CC:DD:EE:03", "rssi": -72},
    {"mac": "AA:BB:CC:DD:EE:04", "rssi": -85},
]

DATA_WIFI_SCAN = {
    TRACKER_DEVICE_ID: {
        "Wi-Fi_Scan_5001": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T10:00:00.000000000Z",
            },
            "Wi-Fi_Scan_5001",
            WIFI_SCAN_DATA,
        )
    }
}

# GPS coordinate data
GPS_LATITUDE = 52.3676
GPS_LONGITUDE = 4.9041

DATA_GPS = {
    TRACKER_DEVICE_ID: {
        "Latitude_4198": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T11:00:00.000000000Z",
            },
            "Latitude_4198",
            GPS_LATITUDE,
        ),
        "Longitude_4197": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T11:00:00.000000000Z",
            },
            "Longitude_4197",
            GPS_LONGITUDE,
        ),
    }
}

# Combined GPS and Wi-Fi data
DATA_GPS_AND_WIFI = {
    TRACKER_DEVICE_ID: {
        "Latitude_4198": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T12:00:00.000000000Z",
            },
            "Latitude_4198",
            GPS_LATITUDE,
        ),
        "Longitude_4197": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T12:00:00.000000000Z",
            },
            "Longitude_4197",
            GPS_LONGITUDE,
        ),
        "Wi-Fi_Scan_5001": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T12:00:00.000000000Z",
            },
            "Wi-Fi_Scan_5001",
            WIFI_SCAN_DATA,
        ),
    }
}

# Battery update (no location data)
DATA_BATTERY_ONLY = {
    TRACKER_DEVICE_ID: {
        "Battery_3": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T13:00:00.000000000Z",
            },
            "Battery_3",
            85,
        )
    }
}

# Wi-Fi scan data with timestamps for out-of-order testing
WIFI_SCAN_DATA_NEW = [
    {"mac": "11:22:33:44:55:01", "rssi": -40},
    {"mac": "11:22:33:44:55:02", "rssi": -60},
]

WIFI_SCAN_DATA_OLD = [
    {"mac": "AA:BB:CC:DD:EE:FF", "rssi": -90},
]

# Newer timestamp (should be used)
DATA_WIFI_NEWER = {
    TRACKER_DEVICE_ID: {
        "Wi-Fi_Scan_5001": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T12:00:00.000000000Z",
                "timestamp": 1710331200000,  # Newer timestamp
            },
            "Wi-Fi_Scan_5001",
            WIFI_SCAN_DATA_NEW,
        )
    }
}

# Older timestamp (should be ignored if received after newer)
DATA_WIFI_OLDER = {
    TRACKER_DEVICE_ID: {
        "Wi-Fi_Scan_5001": TTNSensorValue(
            {
                "end_device_ids": {"device_id": TRACKER_DEVICE_ID},
                "received_at": "2024-03-13T13:00:00.000000000Z",  # Received later
                "timestamp": 1710327600000,  # But measurement is older
            },
            "Wi-Fi_Scan_5001",
            WIFI_SCAN_DATA_OLD,
        )
    }
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=APP_ID,
        title=APP_ID,
        data={
            CONF_APP_ID: APP_ID,
            CONF_HOST: TTN_API_HOST,
            CONF_API_KEY: API_KEY,
        },
    )


@pytest.fixture
def mock_ttnclient():
    """Mock TTNClient."""

    with (
        patch(
            "homeassistant.components.thethingsnetwork.coordinator.TTNClient",
            autospec=True,
        ) as ttn_client,
        patch(
            "homeassistant.components.thethingsnetwork.config_flow.TTNClient",
            new=ttn_client,
        ),
    ):
        instance = ttn_client.return_value
        instance.fetch_data = AsyncMock(return_value=DATA)
        yield ttn_client

"""Common stuff for Vodafone Station tests."""

from io import BytesIO

from aiovodafone.models import DeviceType

DEVICE_1_HOST = "WifiDevice0"
DEVICE_1_MAC = "xx:xx:xx:xx:xx:xx"
DEVICE_2_HOST = "LanDevice1"
DEVICE_2_MAC = "yy:yy:yy:yy:yy:yy"

TEST_HOST = "fake_host"
TEST_PASSWORD = "fake_password"
TEST_TYPE = DeviceType.SERCOMM
TEST_URL = f"https://{TEST_HOST}"
TEST_USERNAME = "fake_username"
TEST_SERIAL_NUMBER = "m123456789"

TEST_WIFI_DATA: dict = {
    "guest": {
        "on": 1,
        "ssid": "Wifi-Guest",
        "qr_code": BytesIO(b"fake-qr-code-guest"),
    },
    "guest_5g": {
        "on": 0,
        "ssid": "Wifi-Guest-5Ghz",
        "qr_code": BytesIO(b"fake-qr-code-guest-5ghz"),
    },
}

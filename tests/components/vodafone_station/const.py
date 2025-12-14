"""Common stuff for Vodafone Station tests."""

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

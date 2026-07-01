"""Constants for the Swisscom Internet-Box integration tests."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

TEST_HOST = "192.168.1.1"
TEST_USERNAME = "admin"
TEST_PASSWORD = "test-password"
TEST_BASE_MAC = "AA:BB:CC:DD:EE:FF"
TEST_FORMATTED_MAC = "aa:bb:cc:dd:ee:ff"
TEST_MODEL_NAME = "Internet-Box plus"

USER_INPUT = {
    CONF_HOST: TEST_HOST,
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
}

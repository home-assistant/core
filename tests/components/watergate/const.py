"""Constants for the Watergate tests."""

from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_WEBHOOK_ID

MOCK_WEBHOOK_ID = "webhook_id"

MOCK_CONFIG = {
    CONF_NAME: "Sonic",
    CONF_IP_ADDRESS: "http://localhost",
    CONF_WEBHOOK_ID: MOCK_WEBHOOK_ID,
}

"""Constants for ruuvi_gateway tests."""
from __future__ import annotations

ASYNC_SETUP_ENTRY = "homeassistant.components.ruuvi_gateway.async_setup_entry"
GET_GATEWAY_HISTORY_DATA = "aioruuvigateway.api.get_gateway_history_data"
EXPECTED_TITLE = "Ruuvi Gateway EE:FF"
BASE_DATA = {
    "host": "1.1.1.1",
    "token": "toktok",
}
GATEWAY_MAC = "AA:BB:CC:DD:EE:FF"
GATEWAY_MAC_LOWER = GATEWAY_MAC.lower()

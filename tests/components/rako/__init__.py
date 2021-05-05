"""Tests for the Rako integration."""
from python_rako import RAKO_BRIDGE_DEFAULT_PORT, BridgeDescription

MOCK_HOST = "192.168.1.11"
MOCK_ENTITY_ID = "my_bridge_id"
MOCK_BRIDGE_NAME = "my_bridge"
MOCK_BRIDGE_MAC = "12-12-12-12-12"

MOCK_BRIDGE_DESC: BridgeDescription = {
    "host": MOCK_HOST,
    "port": RAKO_BRIDGE_DEFAULT_PORT,
    "name": MOCK_BRIDGE_NAME,
    "mac": MOCK_BRIDGE_MAC,
}

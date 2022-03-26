"""Tests for the Rainforest Eagle integration."""


MOCK_CLOUD_ID = "12345"
MOCK_200_RESPONSE_WITH_PRICE = {
    "zigbee:InstantaneousDemand": {
        "Name": "zigbee:InstantaneousDemand",
        "Value": "1.152000",
    },
    "zigbee:CurrentSummationDelivered": {
        "Name": "zigbee:CurrentSummationDelivered",
        "Value": "45251.285000",
    },
    "zigbee:CurrentSummationReceived": {
        "Name": "zigbee:CurrentSummationReceived",
        "Value": "232.232000",
    },
    "zigbee:Price": {"Name": "zigbee:Price", "Value": "0.053990"},
    "zigbee:PriceCurrency": {"Name": "zigbee:PriceCurrency", "Value": "USD"},
}
MOCK_200_RESPONSE_WITHOUT_PRICE = {
    "zigbee:InstantaneousDemand": {
        "Name": "zigbee:InstantaneousDemand",
        "Value": "1.152000",
    },
    "zigbee:CurrentSummationDelivered": {
        "Name": "zigbee:CurrentSummationDelivered",
        "Value": "45251.285000",
    },
    "zigbee:CurrentSummationReceived": {
        "Name": "zigbee:CurrentSummationReceived",
        "Value": "232.232000",
    },
    "zigbee:Price": {"Name": "zigbee:Price", "Value": "invalid"},
    "zigbee:PriceCurrency": {"Name": "zigbee:PriceCurrency", "Value": "USD"},
}

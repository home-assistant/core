"""Tests for the Eurotronic Comet WiFi integration."""

MAC = "AABBCCDDEEFF"
ENTITY_ID = "climate.comet_wifi_aabbccddeeff"

COMMAND_TOPIC_SETPOINT = f"01/{MAC}/S/A0"
COMMAND_TOPIC_REQUEST = f"01/{MAC}/S/AF"
REPLY_TOPIC_SETPOINT = f"01/{MAC}/V/A0"
REPLY_TOPIC_AMBIENT = f"01/{MAC}/V/A1"

# Payloads are "#" + hex of the doubled temperature
PAYLOAD_SETPOINT_21 = "#2A"
PAYLOAD_SETPOINT_23 = "#2E"
PAYLOAD_AMBIENT_22 = "#2C"
PAYLOAD_OFF = "#0F"

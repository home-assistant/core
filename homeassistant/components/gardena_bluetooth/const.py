"""Constants for the Gardena Bluetooth integration."""

DOMAIN = "gardena_bluetooth"
CONF_PRODUCT_TYPE = "product_type"

# Command source written as key 0 of the Valve1/Valve2 start/stop LWM2M
# payload. 18 (0x12) is the Water Control product group the firmware expects
# to mark a command as coming from a Gardena controller.
WATERING_COMMAND_SOURCE = "18"

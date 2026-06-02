"""Constants for the Tonewinner AT-500 integration."""

DOMAIN = "tonewinner"

# Configuration constants
CONF_SERIAL_PORT = "serial_port"
CONF_BAUD_RATE = "baud_rate"

# Options constants
CONF_SOURCE_MAPPINGS = "source_mappings"

# Serial communication constants
DEFAULT_BAUD_RATE = 9600
DEFAULT_TIMEOUT = 1.0
COMMAND_TERMINATOR = "\r\n"

# ISCP Command placeholders (Integra-compatible)
# These will be replaced with actual AT-500 commands when hardware is available
CMD_POWER_ON = "PWR01"
CMD_POWER_OFF = "PWR00"
CMD_POWER_QUERY = "PWRQSTN"
CMD_VOLUME_SET = "MVL"  # Main volume level (00-80 = 0-80 decimal)
CMD_VOLUME_QUERY = "MVLQSTN"
CMD_VOLUME_UP = "MVLUP"
CMD_VOLUME_DOWN = "MVLDOWN"
CMD_MUTE_ON = "AMT01"
CMD_MUTE_OFF = "AMT00"
CMD_MUTE_QUERY = "AMTQSTN"

# Response parsing
RESPONSE_OK = "OK"
RESPONSE_ERROR = "ERR"

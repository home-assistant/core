"""Constants for the Eltako (EnOcean) integration."""

DOMAIN = "eltako_enocean"
MANUFACTURER = "Eltako"

CONF_FAST_STATUS_CHANGE = "fast_status_change"
CONF_GATEWAY_AUTO_RECONNECT = "auto_reconnect"
CONF_GATEWAY_MESSAGE_DELAY = "message_delay"
CONF_SENDER_ID = "sender_id"
CONF_SERIAL_PORT = "serial_port"

ID_REGEX = r"^([0-9a-fA-F]{2})-([0-9a-fA-F]{2})-([0-9a-fA-F]{2})-([0-9a-fA-F]{2})$"

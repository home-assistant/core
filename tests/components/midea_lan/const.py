"""Constants for Midea LAN tests."""

from midealocal.const import ProtocolVersion

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_PORT,
    CONF_PROTOCOL,
)

ENTRY_DATA = {
    CONF_DEVICE_ID: 123,
    CONF_IP_ADDRESS: "1.1.1.1",
    CONF_PORT: 6444,
    CONF_MODEL: "m",
    CONF_PROTOCOL: ProtocolVersion.V2,
}

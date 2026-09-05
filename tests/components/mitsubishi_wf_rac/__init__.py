"""Tests for the Mitsubishi WF-RAC integration."""

from homeassistant.components.mitsubishi_wf_rac.const import (
    CONF_AIRCO_ID,
    CONF_OPERATOR_ID,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_NAME, CONF_PORT

AIRCO_ID = "0011223344aa"
HOST = "192.168.1.4"
PORT = 51443

ENTRY_DATA = {
    CONF_NAME: "Living room",
    CONF_DEVICE_ID: "homeassistant-device-0123456789a",
    CONF_OPERATOR_ID: "hassio-00000000-0000-0000-0000-000000000000",
    CONF_PORT: PORT,
    CONF_AIRCO_ID: AIRCO_ID,
}
ENTRY_OPTIONS = {CONF_HOST: HOST, "availability_retry_limit": 3}

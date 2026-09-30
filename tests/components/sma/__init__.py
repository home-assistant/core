"""Tests for the sma integration."""

from pysma.helpers import DeviceInfo

from homeassistant.components.sma.const import (
    CONF_GROUP,
    CONF_MODBUS,
    CONF_MODBUS_UNIT_ID,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DEVICE = DeviceInfo(
    manufacturer="SMA",
    name="SMA Device Name",
    type="Sunny Boy 3.6",
    serial=123456789,
    sw_version="1.0.0",
)

# SMA protocol tag ids for the "operating_status_general" sensor's raw_value,
# mirroring homeassistant.components.sma.switch._OPERATING_STATUS_OFF_TAG.
OPERATING_STATUS_OFF_TAG = 303
OPERATING_STATUS_ACTIVATED_TAG = 569


MOCK_USER_INPUT = {
    CONF_HOST: "1.1.1.1",
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_GROUP: "user",
    CONF_PASSWORD: "password",
}

MOCK_MODBUS_OPTIONS = {
    CONF_MODBUS: True,
    CONF_PORT: 502,
    CONF_MODBUS_UNIT_ID: 3,
}

MOCK_USER_REAUTH = {
    CONF_PASSWORD: "new_password",
}

MOCK_USER_RECONFIGURE = {
    CONF_HOST: "1.1.1.2",
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_GROUP: "user",
    CONF_PASSWORD: "new_password",
}


MOCK_DHCP_DISCOVERY_INPUT = {
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_GROUP: "user",
    CONF_PASSWORD: "password",
}

MOCK_DHCP_DISCOVERY = {
    CONF_HOST: "1.1.1.1",
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_GROUP: "user",
    CONF_PASSWORD: "password",
    CONF_MAC: "00:15:bb:00:ab:cd",
}


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

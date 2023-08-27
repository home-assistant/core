"""Tests for the Universal Devices ISY/IoX integration."""
from unittest.mock import AsyncMock, Mock, patch

from pyisy import ISY, networking, nodes, programs, variables
from pyisy.constants import CONFIG_NETWORKING, CONFIG_PORTAL

from homeassistant.components.isy994.const import (
    DOMAIN,
    ISY_CONF_FIRMWARE,
    ISY_CONF_MODEL,
    ISY_CONF_NAME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DEVICE_NAME = "Name of the device"
MOCK_UUID = "ce:fb:72:31:b7:b9"
MOCK_MAC = "cefb7231b7b9"
MOCK_POLISY_MAC = "000db9123456"

MOCK_CONFIG_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <app_full_version>5.0.16C</app_full_version>
    <platform>ISY-C-994</platform>
    <root>
        <id>ce:fb:72:31:b7:b9</id>
        <name>Name of the device</name>
    </root>
    <features>
        <feature>
            <id>21040</id>
            <desc>Networking Module</desc>
            <isInstalled>true</isInstalled>
            <isAvailable>true</isAvailable>
        </feature>
    </features>
</configuration>
"""


def _generate_mock_isy() -> Mock:
    """Generate a mock ISY."""
    mock_isy = Mock(spec=ISY)
    mock_isy.initialize = AsyncMock()
    mock_isy.uuid = MOCK_MAC
    mock_isy.configuration = Mock()
    mock_isy.conf = {
        ISY_CONF_NAME: MOCK_DEVICE_NAME,
        ISY_CONF_MODEL: "model",
        ISY_CONF_FIRMWARE: "any",
        CONFIG_NETWORKING: True,
        CONFIG_PORTAL: True,
    }
    mock_isy.nodes = nodes.Nodes(mock_isy, None, None, [], [], [], [])
    mock_isy.programs = programs.Programs(mock_isy, None, [], [], [], [], [])
    mock_isy.variables = variables.Variables(mock_isy, None, None, [], [])
    mock_isy.scenes = []
    mock_isy.websocket = Mock()
    mock_isy.conn = Mock(url="http://127.0.0.1")
    mock_isy.networking = networking.NetworkResources(mock_isy)
    mock_isy.clock = Mock()
    return mock_isy


async def async_init_integration(hass: HomeAssistant) -> ConfigEntry:
    """Set up the ISY994 platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    entry.add_to_hass(hass)
    mock_isy = _generate_mock_isy()
    with patch("homeassistant.components.isy994.ISY", return_value=mock_isy):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry

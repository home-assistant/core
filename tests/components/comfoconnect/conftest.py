"""Test helpers for comfoconnect tests."""

from unittest import mock

import pytest

from homeassistant.components.comfoconnect.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_SENSORS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_bridge():
    """Mock the bridge discover method."""
    with mock.patch(
        "pycomfoconnect.bridge.Bridge.discover"
    ) as mock_bridge_discover, mock.patch(
        "pycomfoconnect.comfoconnect.ComfoConnect.connect"
    ) as mock_connect, mock.patch(
        "pycomfoconnect.comfoconnect.ComfoConnect.disconnect"
    ) as mock_disconnect:
        bridge = mock.Mock(host="1.2.3.4", uuid=b"\x00")
        mock_bridge_discover.return_value = [bridge]
        mock_connect.return_value = True
        mock_disconnect.return_value = True
        yield mock_bridge_discover


@pytest.fixture
def mock_comfoconnect_command():
    """Mock the ComfoConnect connect method."""
    with mock.patch(
        "pycomfoconnect.comfoconnect.ComfoConnect._command"
    ) as mock_command:
        mock_command.return_value = None
        yield mock_command


@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
    """Create a mock ComfoConnect config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
        },
        title="ComfoConnect",
        unique_id="1",
        options={
            CONF_SENSORS: [
                "current_humidity",
                "current_temperature",
                "supply_fan_duty",
                "power_usage",
                "preheater_power_total",
            ]
        },
    )
    entry.add_to_hass(hass)
    return entry

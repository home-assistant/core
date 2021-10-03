"""Test helpers for comfoconnect tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.comfoconnect.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_SENSORS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_bridge():
    """Mock the bridge discover method."""
    with patch("pycomfoconnect.bridge.Bridge.discover") as mock_bridge_discover, patch(
        "pycomfoconnect.comfoconnect.ComfoConnect.connect"
    ) as mock_connect, patch(
        "pycomfoconnect.comfoconnect.ComfoConnect.disconnect"
    ) as mock_disconnect:
        mock_bridge_discover.return_value[0].uuid.hex.return_value = "00"
        mock_connect.return_value = True
        mock_disconnect.return_value = True
        yield mock_bridge_discover


@pytest.fixture
def mock_comfoconnect_command():
    """Mock the ComfoConnect connect method."""
    with patch(
        "pycomfoconnect.comfoconnect.ComfoConnect._command"
    ) as mock_comfoconnect_command:
        mock_comfoconnect_command.return_value = None
        yield mock_comfoconnect_command


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

"""Common fixtures for the SwitchBee Smart Home tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from switchbee.api.central_unit import CUVersion
from switchbee.device import DeviceType, HardwareType, SwitchBeeSwitch

from homeassistant.components.switchbee.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="300F123456",
        version=2,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )


@pytest.fixture
def mock_central_unit() -> Generator[AsyncMock]:
    """Mock the SwitchBee central unit API."""
    devices = {
        device.id: device
        for device in (
            SwitchBeeSwitch(
                id=11,
                name="Ceiling",
                zone="Kitchen",
                type=DeviceType.Switch,
                hardware=HardwareType.RegularSwitch,
            ),
            SwitchBeeSwitch(
                id=21,
                name="Wall",
                zone="Living Room",
                type=DeviceType.Switch,
                hardware=HardwareType.RegularSwitch,
            ),
        )
    }
    with patch(
        "homeassistant.components.switchbee.CentralUnitPolling", autospec=True
    ) as mock_api:
        central_unit = mock_api.return_value
        central_unit.name = "Residence"
        central_unit.mac = "A8-21-08-E7-67-B6"
        central_unit.unique_id = "300F123456"
        central_unit.version = CUVersion("1.4.4(4)")
        central_unit.reconnect_count = 0
        central_unit.devices = devices
        central_unit.module_display.return_value = "Regular Switch"
        yield central_unit

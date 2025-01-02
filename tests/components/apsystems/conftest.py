"""Common fixtures for the APsystems Local API tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from APsystemsEZ1 import ReturnAlarmInfo, ReturnDeviceInfo, ReturnOutputData
import pytest

from homeassistant.components.apsystems.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.apsystems.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_apsystems() -> Generator[MagicMock]:
    """Mock APSystems lib."""
    with (
        patch(
            "homeassistant.components.apsystems.APsystemsEZ1M",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.apsystems.config_flow.APsystemsEZ1M",
            new=mock_client,
        ),
    ):
        mock_api = mock_client.return_value
        mock_api.get_device_info.return_value = ReturnDeviceInfo(
            deviceId="MY_SERIAL_NUMBER",
            devVer="1.0.0",
            ssid="MY_SSID",
            ipAddr="127.0.01",
            minPower=0,
            maxPower=1000,
        )
        mock_api.get_output_data.return_value = ReturnOutputData(
            p1=2.0,
            e1=3.0,
            te1=4.0,
            p2=5.0,
            e2=6.0,
            te2=7.0,
        )
        mock_api.get_alarm_info.return_value = ReturnAlarmInfo(
            offgrid=False,
            shortcircuit_1=True,
            shortcircuit_2=False,
            operating=False,
        )
        mock_api.get_device_power_status.return_value = True
        mock_api.get_max_power.return_value = 666
        yield mock_api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
        },
        unique_id="MY_SERIAL_NUMBER",
    )

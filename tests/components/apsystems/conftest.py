"""Common fixtures for the APsystems Local API tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from APsystemsEZ1 import ReturnAlarmInfo, ReturnDeviceInfo, ReturnOutputData
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.apsystems.const import (
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_LAKE6,
    DOMAIN,
)
from homeassistant.components.apsystems.lake6.client import (
    parse_alarms,
    parse_control_panel,
    parse_device,
    parse_energies,
    parse_modes,
)
from homeassistant.const import CONF_IP_ADDRESS

from . import (
    LAKE6_ACTIVE_PAYLOAD,
    LAKE6_ALARMS_PAYLOAD,
    LAKE6_DEV_ID,
    LAKE6_DEVICES_PAYLOAD,
    LAKE6_ENERGIES_PAYLOAD,
    LAKE6_IDLE_PAYLOAD,
    LAKE6_IP,
    LAKE6_MODES_PAYLOAD,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.apsystems.async_setup_entry",
        return_value=None,
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
            devVer="EZ1 1.0.0",
            ssid="MY_SSID",
            ipAddr="127.0.01",
            minPower=0,
            maxPower=1000,
            isBatterySystem=False,
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


@pytest.fixture
def mock_lake6() -> Generator[MagicMock]:
    """Mock the Lake_6 API client used by the component at runtime."""
    with patch(
        "homeassistant.components.apsystems.Lake6ApiClient", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.async_get_device.return_value = parse_device(LAKE6_DEVICES_PAYLOAD)
        client.async_get_energies.return_value = parse_energies(LAKE6_ENERGIES_PAYLOAD)
        client.async_get_alarms.return_value = parse_alarms(LAKE6_ALARMS_PAYLOAD)
        client.async_get_modes.return_value = parse_modes(LAKE6_MODES_PAYLOAD)
        client.async_get_control_panel.return_value = parse_control_panel(
            LAKE6_IDLE_PAYLOAD
        )
        yield client


@pytest.fixture
def mock_lake6_control_panel() -> Generator[MagicMock]:
    """Mock the Lake_6 API client with a running manual control window."""
    with patch(
        "homeassistant.components.apsystems.Lake6ApiClient", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.async_get_device.return_value = parse_device(LAKE6_DEVICES_PAYLOAD)
        client.async_get_energies.return_value = parse_energies(LAKE6_ENERGIES_PAYLOAD)
        client.async_get_alarms.return_value = parse_alarms(LAKE6_ALARMS_PAYLOAD)
        client.async_get_modes.return_value = parse_modes(LAKE6_MODES_PAYLOAD)
        client.async_get_control_panel.return_value = parse_control_panel(
            LAKE6_ACTIVE_PAYLOAD
        )
        yield client


@pytest.fixture
def mock_lake6_config_flow() -> Generator[MagicMock]:
    """Mock the Lake_6 API client used while probing in the config flow."""
    with patch(
        "homeassistant.components.apsystems.config_flow.Lake6ApiClient",
        autospec=True,
    ) as mock_client:
        mock_client.return_value.async_get_device.return_value = parse_device(
            LAKE6_DEVICES_PAYLOAD
        )
        yield mock_client


@pytest.fixture
def mock_lake6_config_entry() -> MockConfigEntry:
    """Mock a Lake_6 config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_TYPE: DEVICE_TYPE_LAKE6,
            CONF_IP_ADDRESS: LAKE6_IP,
        },
        unique_id=LAKE6_DEV_ID,
        # MockConfigEntry defaults to version 1, which would run the EZ1
        # migration and overwrite device_type.
        version=2,
    )

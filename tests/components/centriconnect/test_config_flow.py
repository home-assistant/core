"""Test the CentriConnect/MyPropane API config flow."""

from unittest.mock import AsyncMock

from aiocentriconnect import Tank
from aiocentriconnect.exceptions import (
    CentriConnectConnectionError,
    CentriConnectConnectionTimeoutError,
    CentriConnectDecodeError,
    CentriConnectEmptyResponseError,
    CentriConnectNotFoundError,
    CentriConnectTooManyRequestsError,
)
import pytest

from homeassistant.components.centriconnect.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_PASSWORD, TEST_TANK_ID, TEST_TANK_NAME, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_ID: TEST_TANK_ID,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert result["result"].unique_id == TEST_TANK_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (CentriConnectNotFoundError, "invalid_auth"),
        (CentriConnectDecodeError("Oh no!", "Bad response"), "unknown"),
        (CentriConnectConnectionTimeoutError, "cannot_connect"),
        (CentriConnectConnectionError, "cannot_connect"),
        (CentriConnectTooManyRequestsError, "cannot_connect"),
        (CentriConnectEmptyResponseError, "unknown"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test flow errors."""
    mock_centriconnect_client.async_get_tank_data.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_ID: TEST_TANK_ID,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    mock_centriconnect_client.async_get_tank_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_ID: TEST_TANK_ID,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert result["result"].unique_id == TEST_TANK_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate devices are rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_ID: TEST_TANK_ID,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


RECONFIGURED_USERNAME = "87654321-2109-6543-98a7-f6edc543210b"
RECONFIGURED_PASSWORD = "654321"


async def _start_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> ConfigFlowResult:
    """Initialize a reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    reconfigure_result = await mock_config_entry.start_reconfigure_flow(hass)

    assert reconfigure_result["type"] is FlowResultType.FORM
    assert reconfigure_result["step_id"] == "reconfigure"

    return await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"],
        {
            CONF_USERNAME: RECONFIGURED_USERNAME,
            CONF_PASSWORD: RECONFIGURED_PASSWORD,
        },
    )


async def _start_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> ConfigFlowResult:
    """Initialize a reauthenticate flow."""
    mock_config_entry.add_to_hass(hass)

    reauthenticate_result = await mock_config_entry.start_reauth_flow(hass)

    assert reauthenticate_result["type"] is FlowResultType.FORM
    assert reauthenticate_result["step_id"] == "reauth_confirm"

    return await hass.config_entries.flow.async_configure(
        reauthenticate_result["flow_id"],
        {
            CONF_USERNAME: RECONFIGURED_USERNAME,
            CONF_PASSWORD: RECONFIGURED_PASSWORD,
        },
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""

    result = await _start_reconfigure_flow(hass, mock_config_entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: RECONFIGURED_USERNAME,
        CONF_PASSWORD: RECONFIGURED_PASSWORD,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure reconfigure flow aborts if the device ID changes."""
    mock_centriconnect_client.async_get_tank_data.return_value = Tank(
        {
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": "different_device_id",
            "DeviceName": TEST_TANK_NAME,
            "DeviceTempCelsius": 17.0,
            "DeviceTempFahrenheit": 63.0,
            "LastPostTimeIso": "2026-02-27 22:00:31.000",
            "Latitude": 40.7128,
            "Longitude": -74.0060,
            "NextPostTimeIso": "2026-02-28 10:00:00.000",
            "SignalQualLTE": -107.0,
            "SolarVolts": 2.46,
            "TankLevel": 75.0,
            "TankSize": 1000,
            "TankSizeUnit": "Gallons",
            "VersionHW": "4.1",
            "VersionLTE": "1.1.2",
        }
    )

    result = await _start_reconfigure_flow(hass, mock_config_entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauthenticate_flow(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthenticate flow."""

    result = await _start_reauth_flow(hass, mock_config_entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: RECONFIGURED_USERNAME,
        CONF_PASSWORD: RECONFIGURED_PASSWORD,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauthenticate_unique_id_mismatch(
    hass: HomeAssistant,
    mock_centriconnect_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure reauthenticate flow aborts if the device ID changes."""
    mock_centriconnect_client.async_get_tank_data.return_value = Tank(
        {
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": "different_device_id",
            "DeviceName": TEST_TANK_NAME,
            "DeviceTempCelsius": 17.0,
            "DeviceTempFahrenheit": 63.0,
            "LastPostTimeIso": "2026-02-27 22:00:31.000",
            "Latitude": 40.7128,
            "Longitude": -74.0060,
            "NextPostTimeIso": "2026-02-28 10:00:00.000",
            "SignalQualLTE": -107.0,
            "SolarVolts": 2.46,
            "TankLevel": 75.0,
            "TankSize": 1000,
            "TankSizeUnit": "Gallons",
            "VersionHW": "4.1",
            "VersionLTE": "1.1.2",
        }
    )

    result = await _start_reauth_flow(hass, mock_config_entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"

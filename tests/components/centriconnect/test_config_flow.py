"""Test the CentriConnect/MyPropane API config flow."""

from unittest.mock import AsyncMock, patch

from aiocentriconnect.exceptions import (
    CentriConnectConnectionError,
    CentriConnectConnectionTimeoutError,
    CentriConnectDecodeError,
    CentriConnectEmptyResponseError,
    CentriConnectNotFoundError,
    CentriConnectTooManyRequestsError,
)

from homeassistant import config_entries
from homeassistant.components.centriconnect.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_PASSWORD, TEST_TANK_ID, TEST_TANK_NAME, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_not_found_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle not found error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiocentriconnect.api.API.async_request",
        side_effect=CentriConnectNotFoundError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_decode_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle decode error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiocentriconnect.api.API.async_request",
        side_effect=CentriConnectDecodeError("Oh no!", "Bad response"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiocentriconnect.api.API.async_request",
        side_effect=Exception("Something went wrong!"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_timeout(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we handle timeout error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiocentriconnect.api.API.async_request",
        side_effect=CentriConnectConnectionTimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiocentriconnect.api.API.async_request",
        side_effect=CentriConnectConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_too_many_requests(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle too many requests error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiocentriconnect.api.API.async_request",
        side_effect=CentriConnectTooManyRequestsError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_empty_response(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle empty response error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiocentriconnect.api.API.async_request",
        side_effect=CentriConnectEmptyResponseError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TANK_NAME
    assert result["data"] == {
        CONF_DEVICE_ID: TEST_TANK_ID,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate devices are rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
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
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_ID: TEST_TANK_ID,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

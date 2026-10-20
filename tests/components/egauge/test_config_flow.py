"""Tests for the eGauge config flow."""

from unittest.mock import MagicMock

from egauge_async.exceptions import EgaugeAuthenticationError, EgaugePermissionError
from httpx2 import ConnectError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.egauge.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "egauge-home"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }
    assert result["result"].unique_id == "ABC123456"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (EgaugeAuthenticationError, "invalid_auth"),
        (EgaugePermissionError, "missing_permission"),
        (ConnectError("Connection error"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_egauge_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user flow with various errors."""
    mock_egauge_client.get_device_serial_number.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrong",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    # Test recovery after error
    mock_egauge_client.get_device_serial_number.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "egauge-home"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }
    assert result["result"].unique_id == "ABC123456"


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuration flow aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "http://192.168.1.200",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test the reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "http://192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "new-secret",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(EgaugeAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(
            EgaugePermissionError, "missing_permission", id="missing_permission"
        ),
        pytest.param(
            ConnectError("Connection error"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    side_effect: type[Exception] | Exception,
    expected_error: str,
) -> None:
    """Test reauthentication flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_egauge_client.get_device_serial_number.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}

    mock_egauge_client.get_device_serial_number.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"


async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test reauthentication aborts when connected to a different device."""
    mock_config_entry.add_to_hass(hass)
    mock_egauge_client.get_device_serial_number.return_value = "XYZ987654"

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_PASSWORD] == "secret"

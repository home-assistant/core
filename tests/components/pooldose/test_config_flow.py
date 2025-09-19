"""Test the PoolDose config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import RequestStatus

from tests.common import MockConfigEntry


async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PoolDose TEST123456789"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "TEST123456789"


async def test_device_unreachable(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that the form shows error when device is unreachable."""
    mock_pooldose_client.is_connected = False
    mock_pooldose_client.connect.return_value = RequestStatus.HOST_UNREACHABLE

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_pooldose_client.is_connected = True
    mock_pooldose_client.connect.return_value = RequestStatus.SUCCESS

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_api_version_unsupported(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that the form shows error when API version is unsupported."""
    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.API_VERSION_UNSUPPORTED,
        {"api_version_is": "v0.9", "api_version_should": "v1.0"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_not_supported"}

    mock_pooldose_client.is_connected = True
    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.SUCCESS,
        {},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_no_device_info(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    device_info: dict[str, Any],
) -> None:
    """Test that the form shows error when device_info is None."""
    mock_pooldose_client.device_info = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_device_info"}

    mock_pooldose_client.device_info = device_info

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("client_status", "expected_error"),
    [
        (RequestStatus.HOST_UNREACHABLE, "cannot_connect"),
        (RequestStatus.PARAMS_FETCH_FAILED, "params_fetch_failed"),
        (RequestStatus.UNKNOWN_ERROR, "cannot_connect"),
    ],
)
async def test_connection_errors(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    client_status: str,
    expected_error: str,
) -> None:
    """Test that the form shows appropriate errors for various connection issues."""
    mock_pooldose_client.connect.return_value = client_status

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_pooldose_client.connect.return_value = RequestStatus.SUCCESS

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_api_no_data(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that the form shows error when API returns NO_DATA."""
    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.NO_DATA,
        {},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_not_set"}

    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.SUCCESS,
        {},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_no_serial_number(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    device_info: dict[str, Any],
) -> None:
    """Test that the form shows error when device_info has no serial number."""
    mock_pooldose_client.device_info = {"NAME": "Pool Device", "MODEL": "POOL DOSE"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_serial_number"}

    mock_pooldose_client.device_info = device_info

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the flow aborts if the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

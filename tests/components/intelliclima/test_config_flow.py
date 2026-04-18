"""Test the IntelliClima config flow."""

from unittest.mock import AsyncMock

from pyintelliclima.api import (
    IntelliClimaAPIError,
    IntelliClimaAuthError,
    IntelliClimaDevices,
)
import pytest

from homeassistant.components.intelliclima.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DATA_CONFIG = {
    CONF_USERNAME: "SuperUser",
    CONF_PASSWORD: "hunter2",
}


async def test_user_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_cloud_interface
) -> None:
    """Test the full config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DATA_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        # invalid_auth
        (IntelliClimaAuthError, "invalid_auth"),
        # cannot_connect
        (IntelliClimaAPIError, "cannot_connect"),
        # unknown
        (RuntimeError("Unexpected error"), "unknown"),
    ],
)
async def test_form_auth_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_cloud_interface: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test we handle authentication-related errors and recover."""
    mock_cloud_interface.authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DATA_CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Recover: clear side effect and complete flow successfully
    mock_cloud_interface.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DATA_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


async def test_form_no_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_cloud_interface: AsyncMock,
    single_eco_device: IntelliClimaDevices,
) -> None:
    """Test we handle no devices found error."""
    # Return empty devices list
    mock_cloud_interface.get_all_device_status.return_value = IntelliClimaDevices(
        ecocomfort2_devices={}, c800_devices={}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DATA_CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}

    # Reset the return_value to its default state
    mock_cloud_interface.get_all_device_status.return_value = single_eco_device

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DATA_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_cloud_interface: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a second config for the same account aborts."""

    mock_config_entry.add_to_hass(hass)

    # Second attempt with the same account
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DATA_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

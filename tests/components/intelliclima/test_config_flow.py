"""Test the IntelliClima config flow."""

from unittest.mock import AsyncMock

from pyintelliclima.api import (
    IntelliClimaAPIError,
    IntelliClimaAuthError,
    IntelliClimaDevices,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.intelliclima.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

DATA_CONFIG = {
    CONF_USERNAME: "SuperUser",
    CONF_PASSWORD: "hunter2",
}


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_cloud_interface
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "errors", "patch_devices"),
    [
        # invalid_auth
        (IntelliClimaAuthError, {"base": "invalid_auth"}, False),
        # cannot_connect
        (IntelliClimaAPIError, {"base": "cannot_connect"}, False),
        # unknown
        (RuntimeError("Unexpected error"), {"base": "unknown"}, False),
    ],
)
async def test_form_auth_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_cloud_interface,
    side_effect,
    errors,
    patch_devices,
) -> None:
    """Test we handle authentication-related errors and recover."""
    mock_cloud_interface.authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    # Recover: clear side effect and complete flow successfully
    mock_cloud_interface.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


async def test_form_no_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_cloud_interface,
    single_eco_device,
) -> None:
    """Test we handle no devices found error."""
    # Return empty devices list
    mock_cloud_interface.get_all_device_status.return_value = IntelliClimaDevices(
        ecocomfort2_devices={}, c800_devices={}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    # Reset to return devices on retry

    # Reset the return_value to its default state
    mock_cloud_interface.get_all_device_status.return_value = single_eco_device

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_cloud_interface,
) -> None:
    """Test creating a second config for the same account aborts."""

    # First successful config entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        DATA_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IntelliClima (SuperUser)"
    assert result["data"] == DATA_CONFIG

    # Second attempt with the same account
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        DATA_CONFIG,
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

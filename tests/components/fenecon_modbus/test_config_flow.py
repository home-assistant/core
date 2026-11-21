"""Test the Fenecon Modbus config flow."""

from unittest.mock import AsyncMock, MagicMock

from fenecon_modbus import (
    FeneconConnectionError,
    FeneconDeviceInfo,
    FeneconInvalidResponseError,
    FeneconTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fenecon_modbus.const import CONF_UNIT_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import HOST, SERIAL

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: 502, CONF_UNIT_ID: 1}


@pytest.mark.usefixtures("mock_fenecon_client")
async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "FENECON Home 10"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "device_info",
    [
        FeneconDeviceInfo(
            openems_version_major=None,
            openems_version_minor=None,
            openems_version_patch=None,
            manufacturer=None,
            manufacturer_model=None,
            manufacturer_options=None,
            manufacturer_version=None,
            manufacturer_serial_number=None,
            manufacturer_ems_serial_number=None,
        )
    ],
)
@pytest.mark.usefixtures("mock_fenecon_client", "mock_setup_entry")
async def test_user_flow_without_identification(hass: HomeAssistant) -> None:
    """Test a FEMS that reports neither model nor serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "FEMS"
    assert result["result"].unique_id is None


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(FeneconConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(FeneconTimeoutError, "cannot_connect", id="timeout"),
        pytest.param(FeneconInvalidResponseError, "not_openems", id="not_openems"),
        pytest.param(RuntimeError, "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_fenecon_client: MagicMock,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test errors in the user flow and that the flow recovers."""
    mock_fenecon_client.read_device_info.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_fenecon_client.read_device_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_fenecon_client")
async def test_user_flow_already_configured_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test aborting when the host and port are already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_fenecon_client")
async def test_user_flow_already_configured_serial(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a known FEMS at a new address updates the existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.168.0.21"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.0.21"

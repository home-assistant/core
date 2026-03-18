"""Tests for JVC Projector config flow."""

from unittest.mock import AsyncMock

from jvcprojector import JvcProjectorAuthError, JvcProjectorConnectError
import pytest

from homeassistant.components.jvc_projector.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_HOST, MOCK_PASSWORD, MOCK_PORT

from tests.common import MockConfigEntry

TARGET = "homeassistant.components.jvc_projector.config_flow.JvcProjector"


@pytest.mark.parametrize("mock_device", [TARGET], indirect=True)
async def test_user_config_flow_success(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test user config flow success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


@pytest.mark.parametrize("mock_device", [TARGET], indirect=True)
async def test_user_config_flow_bad_connect_errors(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test errors when connection error occurs."""
    mock_device.connect.side_effect = JvcProjectorConnectError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Finish flow with success

    mock_device.connect.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


@pytest.mark.parametrize("mock_device", [TARGET], indirect=True)
async def test_user_config_flow_device_exists_abort(
    hass: HomeAssistant, mock_device: AsyncMock, mock_integration: MockConfigEntry
) -> None:
    """Test flow aborts when device already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("mock_device", [TARGET], indirect=True)
async def test_user_config_flow_bad_host_errors(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test errors when bad host error occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "", CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_host"}

    # Finish flow with success

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


@pytest.mark.parametrize("mock_device", [TARGET], indirect=True)
async def test_user_config_flow_bad_auth_errors(
    hass: HomeAssistant, mock_device: AsyncMock
) -> None:
    """Test errors when bad auth error occurs."""
    mock_device.connect.side_effect = JvcProjectorAuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    # Finish flow with success

    mock_device.connect.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT, CONF_PASSWORD: MOCK_PASSWORD},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


@pytest.mark.parametrize("mock_device", [TARGET], indirect=True)
async def test_reauth_config_flow_success(
    hass: HomeAssistant, mock_device: AsyncMock, mock_integration: MockConfigEntry
) -> None:
    """Test reauth config flow success."""
    result = await mock_integration.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: MOCK_PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_integration.data[CONF_HOST] == MOCK_HOST
    assert mock_integration.data[CONF_PORT] == MOCK_PORT
    assert mock_integration.data[CONF_PASSWORD] == MOCK_PASSWORD


@pytest.mark.parametrize("mock_device", [TARGET], indirect=True)
async def test_reauth_config_flow_auth_error(
    hass: HomeAssistant, mock_device: AsyncMock, mock_integration: MockConfigEntry
) -> None:
    """Test reauth config flow when connect fails."""
    mock_device.connect.side_effect = JvcProjectorAuthError

    result = await mock_integration.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: MOCK_PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    # Finish flow with success

    mock_device.connect.side_effect = None

    result = await mock_integration.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: MOCK_PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_integration.data[CONF_HOST] == MOCK_HOST
    assert mock_integration.data[CONF_PORT] == MOCK_PORT
    assert mock_integration.data[CONF_PASSWORD] == MOCK_PASSWORD


@pytest.mark.parametrize("mock_device", [TARGET], indirect=True)
async def test_reauth_config_flow_connect_error(
    hass: HomeAssistant, mock_device: AsyncMock, mock_integration: MockConfigEntry
) -> None:
    """Test reauth config flow when connect fails."""
    mock_device.connect.side_effect = JvcProjectorConnectError

    result = await mock_integration.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: MOCK_PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    # Finish flow with success

    mock_device.connect.side_effect = None

    result = await mock_integration.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: MOCK_PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_integration.data[CONF_HOST] == MOCK_HOST
    assert mock_integration.data[CONF_PORT] == MOCK_PORT
    assert mock_integration.data[CONF_PASSWORD] == MOCK_PASSWORD

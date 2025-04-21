"""Tests for Comelit SimpleHome config flow."""

from unittest.mock import AsyncMock

from aiocomelit import CannotAuthenticate, CannotConnect
from aiocomelit.const import BRIDGE, VEDO
import pytest

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    BRIDGE_HOST,
    BRIDGE_PIN,
    BRIDGE_PORT,
    FAKE_PIN,
    VEDO_HOST,
    VEDO_PIN,
    VEDO_PORT,
)

from tests.common import MockConfigEntry


async def test_flow_serial_bridge(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test starting a flow by user."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: BRIDGE_HOST,
            CONF_PORT: BRIDGE_PORT,
            CONF_PIN: BRIDGE_PIN,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: BRIDGE_HOST,
        CONF_PORT: BRIDGE_PORT,
        CONF_PIN: BRIDGE_PIN,
        CONF_TYPE: BRIDGE,
    }
    assert not result["result"].unique_id
    await hass.async_block_till_done()


async def test_flow_vedo(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
) -> None:
    """Test starting a flow by user."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: VEDO_HOST,
            CONF_PORT: VEDO_PORT,
            CONF_PIN: VEDO_PIN,
            CONF_TYPE: VEDO,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: VEDO_HOST,
        CONF_PORT: VEDO_PORT,
        CONF_PIN: VEDO_PIN,
        CONF_TYPE: VEDO,
    }
    assert not result["result"].unique_id
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (ConnectionResetError, "unknown"),
    ],
)
async def test_exception_connection(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    side_effect,
    error,
) -> None:
    """Test starting a flow by user with a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    mock_vedo.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: VEDO_HOST,
            CONF_PORT: VEDO_PORT,
            CONF_PIN: VEDO_PIN,
            CONF_TYPE: VEDO,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_vedo.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: VEDO_HOST,
            CONF_PORT: VEDO_PORT,
            CONF_PIN: VEDO_PIN,
            CONF_TYPE: VEDO,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == VEDO_HOST
    assert result["data"] == {
        CONF_HOST: VEDO_HOST,
        CONF_PORT: VEDO_PORT,
        CONF_PIN: VEDO_PIN,
        CONF_TYPE: VEDO,
    }


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
) -> None:
    """Test starting a reauthentication flow."""

    mock_vedo_config_entry.add_to_hass(hass)
    result = await mock_vedo_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: FAKE_PIN,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (ConnectionResetError, "unknown"),
    ],
)
async def test_reauth_not_successful(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test starting a reauthentication flow but no connection found."""
    mock_vedo_config_entry.add_to_hass(hass)
    result = await mock_vedo_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_vedo.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: FAKE_PIN,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_vedo.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: VEDO_PIN,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_vedo_config_entry.data[CONF_PIN] == VEDO_PIN

"""Tests for Vodafone Station config flow."""

from unittest.mock import AsyncMock

from aiovodafone import (
    AlreadyLogged,
    CannotAuthenticate,
    CannotConnect,
    ModelNotSupported,
)
import pytest

from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_setup_entry: AsyncMock,
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
            CONF_HOST: "fake_host",
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "fake_host",
        CONF_USERNAME: "fake_username",
        CONF_PASSWORD: "fake_password",
    }
    assert not result["result"].unique_id

    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (AlreadyLogged, "already_logged"),
        (ModelNotSupported, "model_not_supported"),
        (ConnectionResetError, "unknown"),
    ],
)
async def test_exception_connection(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test starting a flow by user with a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    mock_vodafone_station_router.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "fake_host",
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_vodafone_station_router.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "fake_host",
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "fake_host"
    assert result["data"] == {
        "host": "fake_host",
        "username": "fake_username",
        "password": "fake_password",
    }


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test starting a flow by user with a duplicate entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "fake_host",
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test starting a reauthentication flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: "other_fake_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (AlreadyLogged, "already_logged"),
        (ConnectionResetError, "unknown"),
    ],
)
async def test_reauth_not_successful(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test starting a reauthentication flow but no connection found."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_vodafone_station_router.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: "other_fake_password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_vodafone_station_router.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: "fake_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "fake_password"


async def test_options_flow(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CONSIDER_HOME: 37,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_CONSIDER_HOME: 37,
    }

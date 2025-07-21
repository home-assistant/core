"""Test the Homee config flow."""

from unittest.mock import AsyncMock

from pyHomee import HomeeAuthFailedException, HomeeConnectionFailedException
import pytest

from homeassistant.components.homee.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    HOMEE_ID,
    HOMEE_IP,
    HOMEE_NAME,
    NEW_HOMEE_IP,
    NEW_TESTPASS,
    NEW_TESTUSER,
    TESTPASS,
    TESTUSER,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_homee", "mock_config_entry", "mock_setup_entry")
async def test_config_flow(
    hass: HomeAssistant,
) -> None:
    """Test the complete config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["data"] == {
        "host": HOMEE_IP,
        "username": TESTUSER,
        "password": TESTPASS,
    }
    assert result["title"] == f"{HOMEE_NAME} ({HOMEE_IP})"
    assert result["result"].unique_id == HOMEE_ID


@pytest.mark.parametrize(
    ("side_eff", "error"),
    [
        (
            HomeeConnectionFailedException("connection timed out"),
            {"base": "cannot_connect"},
        ),
        (
            HomeeAuthFailedException("wrong username or password"),
            {"base": "invalid_auth"},
        ),
        (
            Exception,
            {"base": "unknown"},
        ),
    ],
)
async def test_config_flow_errors(
    hass: HomeAssistant,
    mock_homee: AsyncMock,
    side_eff: Exception,
    error: dict[str, str],
) -> None:
    """Test the config flow fails as expected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    flow_id = result["flow_id"]

    mock_homee.get_access_token.side_effect = side_eff
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == error

    mock_homee.get_access_token.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_homee")
async def test_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow aborts when already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_homee", "mock_setup_entry")
async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["handler"] == DOMAIN

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: NEW_TESTUSER,
            CONF_PASSWORD: NEW_TESTPASS,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    # Confirm that the config entry has been updated
    assert mock_config_entry.data[CONF_HOST] == HOMEE_IP
    assert mock_config_entry.data[CONF_USERNAME] == NEW_TESTUSER
    assert mock_config_entry.data[CONF_PASSWORD] == NEW_TESTPASS


@pytest.mark.parametrize(
    ("side_eff", "error"),
    [
        (
            HomeeConnectionFailedException("connection timed out"),
            {"base": "cannot_connect"},
        ),
        (
            HomeeAuthFailedException("wrong username or password"),
            {"base": "invalid_auth"},
        ),
        (
            Exception,
            {"base": "unknown"},
        ),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: AsyncMock,
    side_eff: Exception,
    error: dict[str, str],
) -> None:
    """Test reconfigure flow errors."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_homee.get_access_token.side_effect = side_eff
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: NEW_TESTUSER,
            CONF_PASSWORD: NEW_TESTPASS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == error

    # Confirm that the config entry is unchanged
    assert mock_config_entry.data[CONF_USERNAME] == TESTUSER
    assert mock_config_entry.data[CONF_PASSWORD] == TESTPASS

    mock_homee.get_access_token.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: NEW_TESTUSER,
            CONF_PASSWORD: NEW_TESTPASS,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # Confirm that the config entry has been updated
    assert mock_config_entry.data[CONF_HOST] == HOMEE_IP
    assert mock_config_entry.data[CONF_USERNAME] == NEW_TESTUSER
    assert mock_config_entry.data[CONF_PASSWORD] == NEW_TESTPASS


async def test_reauth_wrong_uid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: AsyncMock,
) -> None:
    """Test reauth flow with wrong UID."""
    mock_homee.settings.uid = "wrong_uid"
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: NEW_TESTUSER,
            CONF_PASSWORD: NEW_TESTPASS,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "wrong_hub"

    # Confirm that the config entry is unchanged
    assert mock_config_entry.data[CONF_HOST] == HOMEE_IP


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: AsyncMock,
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_homee
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["handler"] == DOMAIN

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOMEE_IP,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    # Confirm that the config entry has been updated
    assert mock_config_entry.data[CONF_HOST] == NEW_HOMEE_IP
    assert mock_config_entry.data[CONF_USERNAME] == TESTUSER
    assert mock_config_entry.data[CONF_PASSWORD] == TESTPASS


@pytest.mark.parametrize(
    ("side_eff", "error"),
    [
        (
            HomeeConnectionFailedException("connection timed out"),
            {"base": "cannot_connect"},
        ),
        (
            HomeeAuthFailedException("wrong username or password"),
            {"base": "invalid_auth"},
        ),
        (
            Exception,
            {"base": "unknown"},
        ),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: AsyncMock,
    side_eff: Exception,
    error: dict[str, str],
) -> None:
    """Test reconfigure flow errors."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_homee
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_homee.get_access_token.side_effect = side_eff
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOMEE_IP,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == error

    # Confirm that the config entry is unchanged
    assert mock_config_entry.data[CONF_HOST] == HOMEE_IP

    mock_homee.get_access_token.side_effect = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOMEE_IP,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    # Confirm that the config entry has been updated
    assert mock_config_entry.data[CONF_HOST] == NEW_HOMEE_IP
    assert mock_config_entry.data[CONF_USERNAME] == TESTUSER
    assert mock_config_entry.data[CONF_PASSWORD] == TESTPASS


async def test_reconfigure_wrong_uid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homee: AsyncMock,
) -> None:
    """Test reconfigure flow with wrong UID."""
    mock_config_entry.add_to_hass(hass)
    mock_homee.settings.uid = "wrong_uid"
    mock_config_entry.runtime_data = mock_homee
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: NEW_HOMEE_IP,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "wrong_hub"

    # Confirm that the config entry is unchanged
    assert mock_config_entry.data[CONF_HOST] == HOMEE_IP

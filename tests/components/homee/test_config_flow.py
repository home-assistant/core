"""Test the Homee config flow."""

from unittest.mock import AsyncMock

from pyHomee import HomeeAuthFailedException, HomeeConnectionFailedException
import pytest

from homeassistant.components.homee.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOMEE_ID, HOMEE_IP, HOMEE_NAME, TESTPASS, TESTUSER

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

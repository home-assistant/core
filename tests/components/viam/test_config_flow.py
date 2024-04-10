"""Test the viam config flow."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from viam.app.viam_client import ViamClient

from homeassistant import config_entries
from homeassistant.components.viam.config_flow import CannotConnect
from homeassistant.components.viam.const import (
    CONF_API_ID,
    CONF_CREDENTIAL_TYPE,
    CONF_ROBOT,
    CONF_ROBOT_ID,
    CRED_TYPE_API_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@dataclass
class MockLocation:
    """Fake location for testing."""

    id: int = 13
    name: str = "home"


@dataclass
class MockRobot:
    """Fake robot for testing."""

    id: int = 1234
    name: str = "test"


def async_return(result):
    """Allow async return value with MagicMock."""

    future = asyncio.Future()
    future.set_result(result)
    return future


@patch("viam.app.viam_client.ViamClient")
@patch.object(ViamClient, "create_from_dial_options")
async def test_user_form(
    mock_create_client: AsyncMock,
    MockClient: MagicMock,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {}

    instance = MockClient.return_value
    mock_create_client.return_value = instance
    instance.app_client.list_locations.return_value = async_return([MockLocation()])
    instance.app_client.get_location.return_value = async_return(MockLocation())
    instance.app_client.list_robots.return_value = async_return([MockRobot()])

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_ID: "someTestId",
            CONF_API_KEY: "randomSecureAPIKey",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "robot"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ROBOT: "test",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "home"
    assert result["data"] == {
        CONF_API_ID: "someTestId",
        CONF_API_KEY: "randomSecureAPIKey",
        CONF_ROBOT_ID: 1234,
        CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
    }

    assert len(mock_setup_entry.mock_calls) == 1


@patch(
    "viam.app.viam_client.ViamClient.create_from_dial_options",
    side_effect=CannotConnect,
)
async def test_form_cannot_connect(
    _mock_create_client: AsyncMock, hass: HomeAssistant
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_ID: "someTestId",
            CONF_API_KEY: "randomSecureAPIKey",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "cannot_connect"}


@patch(
    "viam.app.viam_client.ViamClient.create_from_dial_options", side_effect=Exception
)
async def test_form_exception(
    _mock_create_client: AsyncMock, hass: HomeAssistant
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_ID: "someTestId",
            CONF_API_KEY: "randomSecureAPIKey",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "unknown"}

"""Test the viam config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from viam.app.viam_client import ViamClient

from homeassistant.components.viam.config_flow import CannotConnect
from homeassistant.components.viam.const import (
    CONF_API_ID,
    CONF_CREDENTIAL_TYPE,
    CONF_ROBOT,
    CONF_ROBOT_ID,
    CONF_SECRET,
    CRED_TYPE_API_KEY,
    CRED_TYPE_LOCATION_SECRET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockRobot

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_viam_client: Generator[tuple[MagicMock, MockRobot], None, None],
) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_api_key"
    assert result["errors"] == {}

    _client, mock_robot = mock_viam_client

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_ID: "someTestId",
            CONF_API_KEY: "randomSecureAPIKey",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "robot"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ROBOT: mock_robot.id,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "home"
    assert result["data"] == {
        CONF_API_ID: "someTestId",
        CONF_API_KEY: "randomSecureAPIKey",
        CONF_ROBOT_ID: mock_robot.id,
        CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_with_location_secret(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_viam_client: Generator[tuple[MagicMock, MockRobot], None, None],
) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CREDENTIAL_TYPE: CRED_TYPE_LOCATION_SECRET,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_robot_location"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: "my.robot.cloud",
            CONF_SECRET: "randomSecreteForRobot",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "robot"

    _client, mock_robot = mock_viam_client

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ROBOT: mock_robot.id,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "home"
    assert result["data"] == {
        CONF_ADDRESS: "my.robot.cloud",
        CONF_SECRET: "randomSecreteForRobot",
        CONF_ROBOT_ID: mock_robot.id,
        CONF_CREDENTIAL_TYPE: CRED_TYPE_LOCATION_SECRET,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_missing_secret(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_api_key"

    with patch(
        "viam.app.viam_client.ViamClient.create_from_dial_options",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_ID: "someTestId",
                CONF_API_KEY: "",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_api_key"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_api_key"

    with patch.object(ViamClient, "create_from_dial_options", return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_ID: "someTestId",
                CONF_API_KEY: "randomSecureAPIKey",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_api_key"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CREDENTIAL_TYPE: CRED_TYPE_API_KEY,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_api_key"

    with patch(
        "viam.app.viam_client.ViamClient.create_from_dial_options",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_ID: "someTestId",
                CONF_API_KEY: "randomSecureAPIKey",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth_api_key"
        assert result["errors"] == {"base": "unknown"}

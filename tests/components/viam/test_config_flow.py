"""Test the viam config flow."""
import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.viam.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.viam.const import DOMAIN
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


async def test_user_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.viam.config_flow.ViamHub",
    ) as MockHub:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "credential_type": "api-key",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {}

        instance = MockHub.return_value
        instance.authenticate.return_value = async_return(True)
        instance.client.app_client.list_locations.return_value = async_return(
            [MockLocation()]
        )
        instance.client.app_client.get_location.return_value = async_return(
            MockLocation()
        )
        instance.client.app_client.list_robots.return_value = async_return(
            [MockRobot()]
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_id": "someTestId",
                "api_key": "randomSecureAPIKey",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] is None
        assert result["step_id"] == "robot"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "robot": "test",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "home"
        assert result["data"] == {
            "api_id": "someTestId",
            "api_key": "randomSecureAPIKey",
            "robot_id": 1234,
            "credential_type": "api-key",
        }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.viam.config_flow.ViamHub.authenticate",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "credential_type": "api-key",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_id": "someTestId",
                "api_key": "randomSecureAPIKey",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.viam.config_flow.ViamHub.authenticate",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_id": "someTestId",
                "api_key": "randomSecureAPIKey",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.viam.config_flow.ViamHub.authenticate",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "credential_type": "api-key",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_id": "someTestId",
                "api_key": "randomSecureAPIKey",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.viam.config_flow.ViamHub.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_id": "someTestId",
                "api_key": "randomSecureAPIKey",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.viam.config_flow.ViamHub.authenticate",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "credential_type": "api-key",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_id": "someTestId",
                "api_key": "randomSecureAPIKey",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "unknown"}

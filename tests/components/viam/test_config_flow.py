"""Test the viam config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from viam.app.viam_client import ViamClient
from viam.rpc.dial import DialOptions

from homeassistant.components.viam.config_flow import CannotConnect
from homeassistant.components.viam.const import (
    CONF_API_ID,
    CONF_LOCATION_ID,
    CONF_MACHINE_ID,
    CONF_ORG_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockLocation, MockMachine, MockOrg

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_viam_client: Generator[tuple[MagicMock, MockOrg, MockLocation, MockMachine]],
) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    _client, mock_org, mock_location, mock_machine = mock_viam_client

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_ID: "someTestId",
            CONF_API_KEY: "randomSecureAPIKey",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{mock_location.name} - {mock_machine.name}"
    assert result["data"] == {
        CONF_API_ID: "someTestId",
        CONF_API_KEY: "randomSecureAPIKey",
        CONF_MACHINE_ID: mock_machine.id,
        CONF_LOCATION_ID: mock_location.id,
        CONF_ORG_ID: mock_org.id,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_missing_secret(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

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
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch.object(DialOptions, "with_api_key", return_value=None),
        patch.object(ViamClient, "create_from_dial_options", return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_ID: "someTestId",
                CONF_API_KEY: "randomSecureAPIKey",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

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
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}

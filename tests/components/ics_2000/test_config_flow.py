"""Test the KlikAanKlikUit ICS-2000 config flow."""

from unittest.mock import AsyncMock, patch

from ics_2000.exceptions import InvalidAuthException
from ics_2000.hub import Hub

from homeassistant import config_entries
from homeassistant.components.ics_2000.const import CONF_HOME_ID, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch.object(Hub, "login", return_value={"5435": "My home"}),
        patch.object(Hub, "select_home", return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My home"
    assert result["data"] == {
        CONF_HOME_ID: "5435",
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch.object(Hub, "login", side_effect=InvalidAuthException),
        patch.object(Hub, "select_home", return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with (
        patch(
            "ics_2000.hub.Hub.login",
            return_value={"5435": "My home"},
        ),
        patch.object(Hub, "select_home", return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My home"
    assert result["data"] == {
        CONF_HOME_ID: "5435",
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_multiple_homes(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle setting a home, if there are multiple."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch.object(
            Hub, "login", return_value={"5435": "My home", "43": "Second home"}
        ),
        patch.object(Hub, "select_home", return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
    assert result["type"] is FlowResultType.FORM

    # Allow the user to select a home
    # After selecting one it should create a entry

    with (
        patch.object(
            Hub, "login", return_value={"5435": "My home", "43": "Second home"}
        ),
        patch.object(Hub, "select_home", return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOME_ID: "5435"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My home"
    assert result["data"] == {
        CONF_HOME_ID: "5435",
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_homes(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test if we get a error if there are no homes available within the account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch.object(Hub, "login", return_value={}),
        patch.object(Hub, "select_home", return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "account_has_no_homes"}

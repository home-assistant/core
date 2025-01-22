"""Test the victronvenus config flow."""

from unittest.mock import AsyncMock, patch

from victronvenusclient import CannotConnectError, InvalidAuthError

from homeassistant import config_entries
from homeassistant.components.victronvenus.const import (
    CONF_INSTALLATION_ID,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.victronvenus.config_flow.validate_input",
        return_value="INSTALLID",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1883,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SSL: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Victron OS INSTALLID"

    assert result["data"][CONF_HOST] == "1.1.1.1"
    assert result["data"][CONF_PORT] == 1883
    assert result["data"][CONF_USERNAME] == "test-username"
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert result["data"][CONF_SSL] == False  # noqa: E712
    assert result["data"][CONF_INSTALLATION_ID] == "INSTALLID"
    assert result["data"][CONF_SERIAL] is None

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronvenus.config_flow.validate_input",
        side_effect=InvalidAuthError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1883,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SSL: False,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.victronvenus.config_flow.validate_input",
        return_value="INSTALLID",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1883,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SSL: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Victron OS INSTALLID"
    assert result["data"][CONF_HOST] == "1.1.1.1"
    assert result["data"][CONF_PORT] == 1883
    assert result["data"][CONF_USERNAME] == "test-username"
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert result["data"][CONF_SSL] == False  # noqa: E712
    assert result["data"][CONF_INSTALLATION_ID] == "INSTALLID"
    assert result["data"][CONF_SERIAL] is None

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.victronvenus.config_flow.validate_input",
        side_effect=CannotConnectError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1883,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SSL: False,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.victronvenus.config_flow.validate_input",
        return_value="INSTALLID",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1883,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SSL: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Victron OS INSTALLID"
    assert result["data"][CONF_HOST] == "1.1.1.1"
    assert result["data"][CONF_PORT] == 1883
    assert result["data"][CONF_USERNAME] == "test-username"
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert result["data"][CONF_SSL] == False  # noqa: E712
    assert result["data"][CONF_INSTALLATION_ID] == "INSTALLID"
    assert result["data"][CONF_SERIAL] is None

    assert len(mock_setup_entry.mock_calls) == 1

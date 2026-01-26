"""Tests for the NRGkick config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.nrgkick.api import (
    NRGkickApiClientApiDisabledError,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import create_mock_config_entry


async def test_form_without_credentials(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we can set up successfully without credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nrgkick.async_setup_entry",
        return_value=True,
    ):
        flow_id = result["flow_id"]
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "NRGkick Test"
    assert result2["data"] == {CONF_HOST: "192.168.1.100"}


async def test_form(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we can setup when authentication is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        flow_id = result["flow_id"]
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    with patch(
        "homeassistant.components.nrgkick.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        flow_id = result2["flow_id"]
        result3 = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_pass",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "NRGkick Test"
    assert result3["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    mock_setup_entry.assert_called_once()


async def test_form_cannot_connect(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_host_input(hass: HomeAssistant) -> None:
    """Test we handle invalid host input during normalization."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "http://"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

    flow_id = result2["flow_id"]
    result3 = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_user_auth_step_cannot_connect(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user auth step reports cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    flow_id = result2["flow_id"]
    result3 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_user_auth_step_unknown_error(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user auth step reports unknown on unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

    flow_id = result2["flow_id"]
    result3 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}


async def test_form_unknown_exception(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_json_api_disabled(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle JSON API disabled error in the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientApiDisabledError

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "json_api_disabled"}


async def test_user_auth_step_json_api_disabled(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user_auth step reports json_api_disabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientApiDisabledError

    flow_id = result2["flow_id"]
    result3 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "json_api_disabled"}


async def test_form_already_configured(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle already configured."""
    entry = create_mock_config_entry(
        domain=DOMAIN,
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.100"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

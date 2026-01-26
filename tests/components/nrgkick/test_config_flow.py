"""Tests for the NRGkick config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

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
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}


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
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    with patch(
        "homeassistant.components.nrgkick.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        flow_id = result["flow_id"]
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_pass",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    mock_setup_entry.assert_called_once()


async def test_form_invalid_host_input(hass: HomeAssistant) -> None:
    """Test we handle invalid host input during normalization."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "http://"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    "scenario",
    [
        {
            "name": "cannot_connect",
            "steps": [
                {
                    "side_effect": NRGkickApiClientCommunicationError,
                    "user_input": {CONF_HOST: "192.168.1.100"},
                    "errors": {"base": "cannot_connect"},
                },
            ],
            "final_user_input": {CONF_HOST: "192.168.1.100"},
            "final_data": {CONF_HOST: "192.168.1.100"},
        },
        {
            "name": "invalid_auth",
            "steps": [
                {
                    "side_effect": NRGkickApiClientAuthenticationError,
                    "user_input": {CONF_HOST: "192.168.1.100"},
                    "step_id": "user_auth",
                },
                {
                    "side_effect": NRGkickApiClientAuthenticationError,
                    "user_input": {
                        CONF_USERNAME: "test-username",
                        CONF_PASSWORD: "test-password",
                    },
                    "errors": {"base": "invalid_auth"},
                },
            ],
            "final_user_input": {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
            "final_data": {
                CONF_HOST: "192.168.1.100",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
            },
        },
    ],
    ids=lambda scenario: scenario["name"],
)
async def test_form_error_then_recovers_to_create_entry(
    hass: HomeAssistant, mock_nrgkick_api, scenario: dict
) -> None:
    """Test errors are handled and the flow can recover to CREATE_ENTRY."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    for step in scenario["steps"]:
        mock_nrgkick_api.test_connection.side_effect = step.get("side_effect")

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            step["user_input"],
        )

        assert result["type"] is FlowResultType.FORM
        if step_id := step.get("step_id"):
            assert result["step_id"] == step_id
        if errors := step.get("errors"):
            assert result["errors"] == errors

        flow_id = result["flow_id"]

    mock_nrgkick_api.test_connection.side_effect = None

    with patch(
        "homeassistant.components.nrgkick.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            scenario["final_user_input"],
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == scenario["final_data"]


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (NRGkickApiClientCommunicationError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
        (NRGkickApiClientApiDisabledError, "json_api_disabled"),
    ],
    ids=["cannot_connect", "unknown", "json_api_disabled"],
)
async def test_user_auth_step_errors(
    hass: HomeAssistant,
    mock_nrgkick_api,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user auth step errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = side_effect

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (NRGkickApiClientError, "unknown"),
        (NRGkickApiClientApiDisabledError, "json_api_disabled"),
    ],
    ids=["unknown", "json_api_disabled"],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_nrgkick_api,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle user step errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = side_effect

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry, mock_nrgkick_api
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

"""Tests for the NRGkick config flow."""

from __future__ import annotations

from unittest.mock import patch

import voluptuous_serialize

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.nrgkick.api import (
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from homeassistant.components.nrgkick.config_flow import STEP_USER_DATA_SCHEMA
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from . import create_mock_config_entry


def test_schema_is_serializable() -> None:
    """Test config flow schemas can be serialized for the UI."""
    voluptuous_serialize.convert(
        STEP_USER_DATA_SCHEMA,
        custom_serializer=cv.custom_serializer,
    )


async def test_form(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we can setup when authentication is required."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {}

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch(
            "homeassistant.components.nrgkick.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("step_id") == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch(
            "homeassistant.components.nrgkick.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        flow_id = result2.get("flow_id")
        assert flow_id is not None
        result3 = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_pass",
            },
        )
        await hass.async_block_till_done()

    assert result3.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "NRGkick Test"
    assert result3.get("data") == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_without_credentials(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we can setup without credentials."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch(
            "homeassistant.components.nrgkick.async_setup_entry",
            return_value=True,
        ),
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result2.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "NRGkick Test"
    assert result2.get("data") == {CONF_HOST: "192.168.1.100"}


async def test_form_cannot_connect(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("step_id") == "user_auth"

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result2.get("flow_id")
        assert flow_id is not None
        result3 = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result3.get("type") == data_entry_flow.FlowResultType.FORM
    assert result3.get("errors") == {"base": "invalid_auth"}


async def test_user_auth_step_cannot_connect(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user auth step reports cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("step_id") == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result2.get("flow_id")
        assert flow_id is not None
        result3 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result3.get("type") == data_entry_flow.FlowResultType.FORM
    assert result3.get("errors") == {"base": "cannot_connect"}


async def test_user_auth_step_unknown_error(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user auth step reports unknown on unexpected error."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("step_id") == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result2.get("flow_id")
        assert flow_id is not None
        result3 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result3.get("type") == data_entry_flow.FlowResultType.FORM
    assert result3.get("errors") == {"base": "unknown"}


async def test_user_auth_step_no_serial_number(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user auth step reports no_serial_number when missing."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("step_id") == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None
    mock_nrgkick_api.get_info.return_value = {
        "general": {"device_name": "NRGkick Test"}
    }

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result2.get("flow_id")
        assert flow_id is not None
        result3 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result3.get("type") == data_entry_flow.FlowResultType.FORM
    assert result3.get("errors") == {"base": "no_serial_number"}


async def test_form_no_serial_number(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle missing serial number."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.get_info.return_value = {
        "general": {
            "device_name": "NRGkick Test",
            # serial_number missing
            "rated_current": 32.0,
        }
    }

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"base": "no_serial_number"}


async def test_form_unknown_exception(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle already configured."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.100"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        flow_id = result.get("flow_id")
        assert flow_id is not None
        result2 = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"

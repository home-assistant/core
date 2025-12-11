"""Tests for Lytiva config flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_user_success(hass: HomeAssistant) -> None:
    """Test successful config flow."""
    with patch(
        "homeassistant.components.lytiva.config_flow.mqtt_client.Client"
    ) as mock_client:
        # Mock successful connection
        client_instance = MagicMock()
        mock_client.return_value = client_instance

        def mock_connect(broker, port, timeout):
            return 0

        def mock_loop(timeout):
            # Trigger on_connect with success
            if client_instance.on_connect:
                client_instance.on_connect(client_instance, None, {}, 0, None)
            return 0

        client_instance.connect = mock_connect
        client_instance.loop = mock_loop
        client_instance.disconnect = MagicMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                "port": 1883,
                "username": "test_user",
                "password": "test_pass",
            },
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Lytiva (192.168.1.100)"
        assert result2["data"] == {
            "broker": "192.168.1.100",
            "port": 1883,
            "username": "test_user",
            "password": "test_pass",
        }


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.lytiva.config_flow.mqtt_client.Client"
    ) as mock_client:
        # Mock connection failure
        client_instance = MagicMock()
        mock_client.return_value = client_instance

        def mock_connect(broker, port, timeout):
            raise Exception("Connection failed")

        client_instance.connect = mock_connect

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                "port": 1883,
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error."""
    with patch(
        "homeassistant.components.lytiva.config_flow.mqtt_client.Client"
    ) as mock_client:
        # Mock auth failure
        client_instance = MagicMock()
        mock_client.return_value = client_instance

        def mock_connect(broker, port, timeout):
            return 0

        def mock_loop(timeout):
            # Trigger on_connect with auth error (reason_code=4)
            if client_instance.on_connect:
                client_instance.on_connect(client_instance, None, {}, 4, None)
            return 0

        client_instance.connect = mock_connect
        client_instance.loop = mock_loop
        client_instance.disconnect = MagicMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                "port": 1883,
                "username": "wrong_user",
                "password": "wrong_pass",
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_other_connection_error(hass: HomeAssistant) -> None:
    """Test we handle other connection errors."""
    with patch(
        "homeassistant.components.lytiva.config_flow.mqtt_client.Client"
    ) as mock_client:
        # Mock other connection error
        client_instance = MagicMock()
        mock_client.return_value = client_instance

        def mock_connect(broker, port, timeout):
            return 0

        def mock_loop(timeout):
            # Trigger on_connect with other error (reason_code=5)
            if client_instance.on_connect:
                client_instance.on_connect(client_instance, None, {}, 5, None)
            return 0

        client_instance.connect = mock_connect
        client_instance.loop = mock_loop
        client_instance.disconnect = MagicMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                "port": 1883,
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we handle already configured."""
    # First, set up an entry
    with patch(
        "homeassistant.components.lytiva.config_flow.mqtt_client.Client"
    ) as mock_client:
        client_instance = MagicMock()
        mock_client.return_value = client_instance

        def mock_connect(broker, port, timeout):
            return 0

        def mock_loop(timeout):
            if client_instance.on_connect:
                client_instance.on_connect(client_instance, None, {}, 0, None)
            return 0

        client_instance.connect = mock_connect
        client_instance.loop = mock_loop
        client_instance.disconnect = MagicMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                "port": 1883,
            },
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY

        # Try to configure the same broker again
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                "broker": "192.168.1.100",
                "port": 1883,
            },
        )

        assert result4["type"] == FlowResultType.ABORT
        assert result4["reason"] == "already_configured"


async def test_form_with_username_no_password(hass: HomeAssistant) -> None:
    """Test config flow with username but no password."""
    with patch(
        "homeassistant.components.lytiva.config_flow.mqtt_client.Client"
    ) as mock_client:
        client_instance = MagicMock()
        mock_client.return_value = client_instance

        def mock_connect(broker, port, timeout):
            return 0

        def mock_loop(timeout):
            if client_instance.on_connect:
                client_instance.on_connect(client_instance, None, {}, 0, None)
            return 0

        client_instance.connect = mock_connect
        client_instance.loop = mock_loop
        client_instance.disconnect = MagicMock()
        client_instance.username_pw_set = MagicMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                "port": 1883,
                "username": "test_user",
                "password": "",
            },
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        # Verify username_pw_set was called
        client_instance.username_pw_set.assert_called_once_with("test_user", "")

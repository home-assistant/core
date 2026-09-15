"""Test the Remootio config flow."""

import asyncio
from unittest.mock import AsyncMock, patch

from pyremootio import (
    RemootioAuthenticationError,
    RemootioConnectionError,
    RemootioCryptoError,
    RemootioTimeoutError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.remootio.const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    DOMAIN,
    device_name,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_SERIAL,
    REAUTH_INPUT,
    RECONFIGURE_HOST,
    RECONFIGURE_HOST_INPUT,
    RECONFIGURE_KEYS_INPUT,
    USER_INPUT,
)

from tests.common import MockConfigEntry, get_schema_suggested_value


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test we get the form and can create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_name(MOCK_SERIAL)
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == MOCK_SERIAL
    assert len(mock_setup_entry.mock_calls) == 1
    mock_remootio_client.__aenter__.assert_awaited()
    mock_remootio_client.__aexit__.assert_awaited()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ValueError("secret_key must be a 64-character hex string"), "invalid_auth"),
        (RemootioAuthenticationError("auth failed"), "invalid_auth"),
        (RemootioCryptoError("mac mismatch"), "invalid_auth"),
        (RemootioConnectionError("offline"), "cannot_connect"),
        (RemootioTimeoutError("timeout"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test we handle errors and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_cls = "homeassistant.components.remootio.config_flow.RemootioClient"
    if isinstance(side_effect, ValueError):
        with patch(mock_cls, side_effect=side_effect):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], USER_INPUT
            )
    else:
        mock_remootio_client.__aenter__.side_effect = side_effect
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        mock_remootio_client.__aenter__.side_effect = None
        mock_remootio_client.__aenter__.return_value = mock_remootio_client

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_name(MOCK_SERIAL)
    assert result["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_missing_serial(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test we treat a missing serial after connect as cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_remootio_client.serial_number = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_remootio_client.serial_number = MOCK_SERIAL
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_name(MOCK_SERIAL)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort when the serial is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauth_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth updates keys and reloads."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert "translation_domain" not in result
    assert mock_config_entry.data[CONF_HOST] == USER_INPUT[CONF_HOST]
    assert (
        mock_config_entry.data[CONF_API_SECRET_KEY] == REAUTH_INPUT[CONF_API_SECRET_KEY]
    )
    assert mock_config_entry.data[CONF_API_AUTH_KEY] == REAUTH_INPUT[CONF_API_AUTH_KEY]


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ValueError("secret_key must be a 64-character hex string"), "invalid_auth"),
        (RemootioAuthenticationError("auth failed"), "invalid_auth"),
        (RemootioCryptoError("mac mismatch"), "invalid_auth"),
        (RemootioConnectionError("offline"), "cannot_connect"),
        (RemootioTimeoutError("timeout"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test reauth handles errors and can recover."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_cls = "homeassistant.components.remootio.config_flow.RemootioClient"
    if isinstance(side_effect, ValueError):
        with patch(mock_cls, side_effect=side_effect):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], REAUTH_INPUT
            )
    else:
        mock_remootio_client.__aenter__.side_effect = side_effect
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], REAUTH_INPUT
        )
        mock_remootio_client.__aenter__.side_effect = None
        mock_remootio_client.__aenter__.return_value = mock_remootio_client

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_unique_id_mismatch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth aborts when the keys belong to a different device."""
    mock_config_entry.add_to_hass(hass)
    mock_remootio_client.serial_number = "other-serial"

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == USER_INPUT


async def test_reconfigure_host_keeps_keys(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure updates host and keeps stored API keys when keys are blank."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_HOST) == USER_INPUT[CONF_HOST]
    assert get_schema_suggested_value(schema, CONF_API_SECRET_KEY) is None
    assert get_schema_suggested_value(schema, CONF_API_AUTH_KEY) is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_HOST_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert "translation_domain" not in result
    assert mock_config_entry.data[CONF_HOST] == RECONFIGURE_HOST
    assert (
        mock_config_entry.data[CONF_API_SECRET_KEY] == USER_INPUT[CONF_API_SECRET_KEY]
    )
    assert mock_config_entry.data[CONF_API_AUTH_KEY] == USER_INPUT[CONF_API_AUTH_KEY]


async def test_reconfigure_updates_keys(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure can replace API keys."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_KEYS_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == RECONFIGURE_HOST
    assert (
        mock_config_entry.data[CONF_API_SECRET_KEY]
        == RECONFIGURE_KEYS_INPUT[CONF_API_SECRET_KEY]
    )
    assert (
        mock_config_entry.data[CONF_API_AUTH_KEY]
        == RECONFIGURE_KEYS_INPUT[CONF_API_AUTH_KEY]
    )


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (ValueError("secret_key must be a 64-character hex string"), "invalid_auth"),
        (RemootioAuthenticationError("auth failed"), "invalid_auth"),
        (RemootioCryptoError("mac mismatch"), "invalid_auth"),
        (RemootioConnectionError("offline"), "cannot_connect"),
        (RemootioTimeoutError("timeout"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test reconfigure handles errors and can recover."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_cls = "homeassistant.components.remootio.config_flow.RemootioClient"
    if isinstance(side_effect, ValueError):
        with patch(mock_cls, side_effect=side_effect):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], RECONFIGURE_KEYS_INPUT
            )
    else:
        mock_remootio_client.__aenter__.side_effect = side_effect
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_KEYS_INPUT
        )
        mock_remootio_client.__aenter__.side_effect = None
        mock_remootio_client.__aenter__.return_value = mock_remootio_client

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_KEYS_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_remootio_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure aborts when the host is a different device."""
    mock_config_entry.add_to_hass(hass)
    mock_remootio_client.serial_number = "other-serial"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_HOST_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == USER_INPUT


async def test_reconfigure_restores_runtime_after_probe_failure(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test reconfigure disconnects the live client, then reconnects if the probe fails."""
    result = await init_integration.start_reconfigure_flow(hass)
    mock_remootio_client.connect.reset_mock()
    mock_remootio_client.enable_reconnect.reset_mock()
    mock_remootio_client.disconnect.reset_mock()

    mock_remootio_client.__aenter__.side_effect = RemootioTimeoutError(
        "No SERVER_HELLO"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_HOST_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_remootio_client.disconnect.assert_awaited_once()
    mock_remootio_client.connect.assert_awaited_once_with(reconnect=True)
    mock_remootio_client.enable_reconnect.assert_not_called()
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.data == USER_INPUT


async def test_reconfigure_restores_runtime_on_unique_id_mismatch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test reconfigure restores the live client when the serial does not match."""
    result = await init_integration.start_reconfigure_flow(hass)
    mock_remootio_client.connect.reset_mock()
    mock_remootio_client.enable_reconnect.reset_mock()
    mock_remootio_client.serial_number = "other-serial"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_HOST_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    mock_remootio_client.connect.assert_awaited_once_with(reconnect=True)
    mock_remootio_client.enable_reconnect.assert_not_called()
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.data == USER_INPUT


async def test_reauth_restores_runtime_after_probe_failure(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test reauth disconnects the live client, then reconnects if the probe fails."""
    result = await init_integration.start_reauth_flow(hass)
    mock_remootio_client.connect.reset_mock()
    mock_remootio_client.enable_reconnect.reset_mock()
    mock_remootio_client.disconnect.reset_mock()

    mock_remootio_client.__aenter__.side_effect = RemootioTimeoutError(
        "No SERVER_HELLO"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_remootio_client.disconnect.assert_awaited_once()
    mock_remootio_client.connect.assert_awaited_once_with(reconnect=True)
    mock_remootio_client.enable_reconnect.assert_not_called()
    assert init_integration.state is ConfigEntryState.LOADED


async def test_reauth_restores_runtime_on_unique_id_mismatch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test reauth restores the live client when the keys belong to another device."""
    result = await init_integration.start_reauth_flow(hass)
    mock_remootio_client.connect.reset_mock()
    mock_remootio_client.enable_reconnect.reset_mock()
    mock_remootio_client.serial_number = "other-serial"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    mock_remootio_client.connect.assert_awaited_once_with(reconnect=True)
    mock_remootio_client.enable_reconnect.assert_not_called()
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.data == USER_INPUT


async def test_reconfigure_restores_runtime_when_probe_is_cancelled(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test cancelling a probe restores the live client with reconnect enabled."""
    result = await init_integration.start_reconfigure_flow(hass)
    mock_remootio_client.connect.reset_mock()
    mock_remootio_client.disconnect.reset_mock()
    mock_remootio_client.__aenter__.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_HOST_INPUT
        )

    mock_remootio_client.disconnect.assert_awaited_once()
    mock_remootio_client.connect.assert_awaited_once_with(reconnect=True)

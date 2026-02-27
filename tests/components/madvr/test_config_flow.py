"""Test config flow for madVR Envy."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from homeassistant.components.madvr.const import (
    DOMAIN,
    OPT_RECONNECT_INITIAL_BACKOFF,
    OPT_RECONNECT_JITTER,
    OPT_RECONNECT_MAX_BACKOFF,
)


async def test_user_flow_success(hass):
    """Test successful config flow."""
    client = MagicMock()
    client.start = AsyncMock()
    client.wait_synced = AsyncMock()
    client.stop = AsyncMock()
    client.state = SimpleNamespace(mac_address="00:11:22:33:44:55")

    with patch("homeassistant.components.madvr.config_flow.MadvrEnvyClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: "192.168.1.100", CONF_PORT: 44077},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "madVR Envy (00:11:22:33:44:55)"
    assert result["data"] == {CONF_HOST: "192.168.1.100", CONF_PORT: 44077}


async def test_user_flow_cannot_connect(hass):
    """Test user flow connection failure."""
    client = MagicMock()
    client.start = AsyncMock(side_effect=TimeoutError)
    client.stop = AsyncMock()

    with patch("homeassistant.components.madvr.config_flow.MadvrEnvyClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: "192.168.1.100", CONF_PORT: 44077},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_exception_maps_to_cannot_connect(hass):
    """Test unexpected validation exception doesn't crash flow."""
    client = MagicMock()
    client.start = AsyncMock(side_effect=RuntimeError("boom"))
    client.stop = AsyncMock()

    with patch("homeassistant.components.madvr.config_flow.MadvrEnvyClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: "192.168.1.100", CONF_PORT: 44077},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_success_without_mac(hass):
    """Test successful config flow when MAC is not available."""
    client = MagicMock()
    client.start = AsyncMock()
    client.wait_synced = AsyncMock()
    client.stop = AsyncMock()
    client.state = SimpleNamespace(mac_address=None)

    with patch("homeassistant.components.madvr.config_flow.MadvrEnvyClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: "192.168.1.100", CONF_PORT: 44077},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "madVR Envy (192.168.1.100)"


async def test_reauth_flow_success(hass, mock_config_entry):
    """Test successful reauth."""
    mock_config_entry.add_to_hass(hass)

    client = MagicMock()
    client.start = AsyncMock()
    client.wait_synced = AsyncMock()
    client.stop = AsyncMock()
    client.state = SimpleNamespace(mac_address="00:11:22:33:44:55")

    with (
        patch("homeassistant.components.madvr.config_flow.MadvrEnvyClient", return_value=client),
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(),
        ) as mock_reload,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
            data=mock_config_entry.data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_reload.await_count == 1


async def test_options_flow_invalid_backoff(hass, mock_config_entry):
    """Test options flow validates reconnect backoff ordering."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "sync_timeout": 10.0,
            "connect_timeout": 3.0,
            "command_timeout": 2.0,
            "read_timeout": 30.0,
            OPT_RECONNECT_INITIAL_BACKOFF: 5.0,
            OPT_RECONNECT_MAX_BACKOFF: 2.0,
            OPT_RECONNECT_JITTER: 0.2,
            "enable_advanced_entities": True,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_backoff"}


async def test_options_flow_invalid_jitter(hass, mock_config_entry):
    """Test options flow validates reconnect jitter bounds."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "sync_timeout": 10.0,
                "connect_timeout": 3.0,
                "command_timeout": 2.0,
                "read_timeout": 30.0,
                OPT_RECONNECT_INITIAL_BACKOFF: 1.0,
                OPT_RECONNECT_MAX_BACKOFF: 2.0,
                OPT_RECONNECT_JITTER: 1.5,
                "enable_advanced_entities": True,
            },
        )


async def test_options_flow_success(hass, mock_config_entry):
    """Test options flow saves valid options."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "sync_timeout": 11.0,
            "connect_timeout": 4.0,
            "command_timeout": 3.0,
            "read_timeout": 15.0,
            OPT_RECONNECT_INITIAL_BACKOFF: 0.5,
            OPT_RECONNECT_MAX_BACKOFF: 8.0,
            OPT_RECONNECT_JITTER: 0.1,
            "enable_advanced_entities": False,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY

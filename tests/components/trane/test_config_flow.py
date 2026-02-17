"""Tests for the Trane Local config flow."""

from unittest.mock import MagicMock

import pytest
from steamloop import PairingError, SteamloopConnectionError

from homeassistant.components.trane.const import CONF_SECRET_KEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST, MOCK_SECRET_KEY


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_connection: MagicMock,
) -> None:
    """Test the full user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Thermostat ({MOCK_HOST})"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_SECRET_KEY: MOCK_SECRET_KEY,
    }
    assert result["result"].unique_id is None


@pytest.mark.parametrize(
    "side_effect",
    [SteamloopConnectionError, PairingError],
)
async def test_connection_error(
    hass: HomeAssistant,
    mock_connection: MagicMock,
    side_effect: Exception,
) -> None:
    """Test config flow with connection errors."""
    mock_connection.pair.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unknown_error(
    hass: HomeAssistant,
    mock_connection: MagicMock,
) -> None:
    """Test config flow with an unexpected exception."""
    mock_connection.pair.side_effect = RuntimeError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_already_configured(
    hass: HomeAssistant,
    mock_connection: MagicMock,
    mock_config_entry,
) -> None:
    """Test config flow aborts when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

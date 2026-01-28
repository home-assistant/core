"""Tests for the Hidromotic config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.hidromotic.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, MOCK_DATA

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_config_flow_client: MagicMock,
) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result.get("errors")

    with patch(
        "homeassistant.components.hidromotic.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"CHI Smart ({HOST})"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == HOST
    assert len(mock_setup.mock_calls) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test config flow when device cannot be reached."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.hidromotic.config_flow.HidromoticClient",
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.connect = AsyncMock(return_value=False)
        client.disconnect = AsyncMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test config flow when an unknown error occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hidromotic.config_flow.HidromoticClient",
        side_effect=Exception("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_flow_client: MagicMock,
) -> None:
    """Test config flow when device is already configured."""
    # Create existing config entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        data={CONF_HOST: HOST},
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_mini_device(
    hass: HomeAssistant,
) -> None:
    """Test config flow with a CHI Smart Mini device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mini_data = {**MOCK_DATA, "is_mini": True}

    with (
        patch(
            "homeassistant.components.hidromotic.config_flow.HidromoticClient",
        ) as mock_client_class,
        patch(
            "homeassistant.components.hidromotic.async_setup_entry",
            return_value=True,
        ),
    ):
        client = mock_client_class.return_value
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.data = mini_data

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"CHI Smart Mini ({HOST})"

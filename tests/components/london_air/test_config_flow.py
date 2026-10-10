"""Tests for the London Air config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError

from homeassistant.components.london_air.const import CONF_LOCATIONS, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user(
    hass: HomeAssistant,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    with patch(
        "homeassistant.components.london_air.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_LOCATIONS: ["Merton"]}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "London Air"
        assert result["data"] == {CONF_LOCATIONS: ["Merton"]}
        assert result["result"].unique_id == DOMAIN
        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_user_required(
    hass: HomeAssistant,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the user config flow with no locations selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCATIONS: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_LOCATIONS: "required"}

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCATIONS: ["Merton"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_user_cannot_connect(
    hass: HomeAssistant,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the user config flow when the API is unreachable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientResponseError(None, None, status=503)
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCATIONS: ["Merton"]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCATIONS: ["Merton"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_user_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Test the user config flow aborts when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientResponseError(None, None, status=503)
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LOCATIONS: ["Merton"]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import(
    hass: HomeAssistant,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test importing from YAML configuration."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_LOCATIONS: ["Merton"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Air"
    assert result["data"] == {CONF_LOCATIONS: ["Merton"]}
    assert result["result"].unique_id == DOMAIN


async def test_import_cannot_connect(
    hass: HomeAssistant,
    mock_session: MagicMock,
) -> None:
    """Test importing from YAML when the API is unreachable."""
    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientResponseError(None, None, status=503)
        )
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_LOCATIONS: ["Merton"]},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

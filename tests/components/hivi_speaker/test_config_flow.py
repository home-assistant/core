"""Tests for the HiVi Speaker config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.hivi_speaker.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user config flow: add integration, create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HiVi Speaker"
    assert result["data"] == {}
    assert result["result"].unique_id == DOMAIN

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_second_flow_aborts_when_unique_id_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a second user flow aborts: unique_id is already taken (_abort_if_unique_id_configured)."""
    mock_config_entry.add_to_hass(hass)

    # Ensure translation for abort reason is available (integration strings.json may not be loaded in test env)
    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        new_callable=AsyncMock,
        return_value={
            "config.abort.already_configured": "Already configured."
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_options_flow_init_step(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow: initial step shows form with confirm_refresh."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id,
        data=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "data_schema" in result


async def test_options_flow_skip_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow: user unchecks confirm_refresh -> entry updated, no refresh."""
    mock_config_entry.add_to_hass(hass)
    mock_dm = AsyncMock()
    mock_dm.refresh_discovery = AsyncMock()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = {"device_manager": mock_dm}

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id,
        data=None,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"confirm_refresh": False},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {}
    mock_dm.refresh_discovery.assert_not_called()


async def test_options_flow_confirm_refresh_then_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow: user confirms refresh -> device_manager.refresh_discovery -> success."""
    mock_config_entry.add_to_hass(hass)
    mock_dm = AsyncMock()
    mock_dm.refresh_discovery = AsyncMock()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = {"device_manager": mock_dm}

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id,
        data=None,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"confirm_refresh": True},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "success"
    mock_dm.refresh_discovery.assert_awaited_once()

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY

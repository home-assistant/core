"""Tests for the HiVi Speaker config flow."""

from unittest.mock import AsyncMock, patch

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
    assert result["result"].unique_id is None

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_single_instance_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a second config flow aborts with single_instance_allowed."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
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
    """Test options flow: user unchecks confirm_refresh -> entry updated, no service call."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        hass.services,
        "async_call",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_async_call:
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
        mock_async_call.assert_not_called()


async def test_options_flow_confirm_refresh_then_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow: user confirms refresh -> service called -> success step -> done."""
    mock_config_entry.add_to_hass(hass)

    # Mock service call so flow does not depend on integration being fully set up
    with patch.object(
        hass.services,
        "async_call",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_async_call:
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

        # Flow shows success step (form with message)
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "success"

        mock_async_call.assert_called_once_with(
            DOMAIN, "refresh_discovery", {}, blocking=False
        )

        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={},
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY

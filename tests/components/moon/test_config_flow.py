"""Tests for the Moon config flow."""
from unittest.mock import MagicMock

from homeassistant.components.moon.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Moon"
    assert result2.get("data") == {}


async def test_single_instance_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already setup."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"

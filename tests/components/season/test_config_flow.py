"""Tests for the Season config flow."""

from unittest.mock import MagicMock

from homeassistant.components.season.const import DOMAIN, TYPE_ASTRONOMICAL
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TYPE
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

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TYPE: TYPE_ASTRONOMICAL},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Season"
    assert result2.get("data") == {CONF_TYPE: TYPE_ASTRONOMICAL}


async def test_single_instance_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already setup."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_TYPE: TYPE_ASTRONOMICAL}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"

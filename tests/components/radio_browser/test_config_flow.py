"""Test the Radio Browser config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.radio_browser.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Radio Browser"
    assert result2.get("data") == {}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we abort if the Radio Browser is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_onboarding_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the onboarding configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "onboarding"}
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Radio Browser"
    assert result.get("data") == {}

    assert len(mock_setup_entry.mock_calls) == 1

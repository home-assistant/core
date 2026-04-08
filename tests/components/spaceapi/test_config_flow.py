"""Test the SpaceAPI config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.spaceapi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    "space": "Home",
    "logo": "https://home-assistant.io/logo.png",
    "url": "https://home-assistant.io",
    "entity_id": "binary_sensor.front_door",
    "email": "hello@home-assistant.io",
    "issue_report_channels": ["email"],
}


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the happy path of the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == {
        "space": "Home",
        "logo": "https://home-assistant.io/logo.png",
        "url": "https://home-assistant.io",
        "state": {"entity_id": "binary_sensor.front_door"},
        "contact": {"email": "hello@home-assistant.io"},
        "issue_report_channels": ["email"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the user flow aborts when an entry already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Existing",
            "logo": "https://example.com/logo.png",
            "url": "https://example.com",
            "state": {"entity_id": "binary_sensor.door"},
            "contact": {"email": "test@example.com"},
            "issue_report_channels": ["email"],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0

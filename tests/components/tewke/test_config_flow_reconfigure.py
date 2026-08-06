"""Test the Tewke reconfigure flow."""

from unittest.mock import AsyncMock

from homeassistant.components.tewke.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_reconfigure_flow(hass: HomeAssistant, mock_tap: AsyncMock) -> None:
    """Test reconfigure flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_dock_id",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Tewke Switch",
            "room_name": "Living Room",
        },
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirmation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

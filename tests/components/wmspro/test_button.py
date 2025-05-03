"""Test the wmspro button support."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import setup_config_entry

from tests.common import MockConfigEntry


async def test_button_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_awning_dimmer: AsyncMock,
    mock_hub_status_prod_awning: AsyncMock,
    mock_action_call: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a button entity is created and updated correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_awning_dimmer.mock_calls) == 1
    assert len(mock_hub_status_prod_awning.mock_calls) == 2

    entity = hass.states.get("button.markise_identify")
    assert entity is not None
    assert entity == snapshot

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_awning.mock_calls)
        before_state = entity.state

        await hass.services.async_call(
            Platform.BUTTON,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("button.markise_identify")
        assert entity is not None
        assert entity.state != before_state
        assert len(mock_hub_status_prod_awning.mock_calls) == before

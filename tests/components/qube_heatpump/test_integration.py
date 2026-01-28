"""Integration tests for the Qube Heat Pump component."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.qube_heatpump.const import CONF_HOST, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_setup_with_entities(
    hass: HomeAssistant, mock_qube_client: MagicMock
) -> None:
    """Test full setup including entity creation and state update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        title="Qube Heat Pump",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check that an entity was created and has a state.
    states = hass.states.async_all()
    assert len(states) > 0, "No entities were created"

    # Verify at least one specific sensor is available
    qube_entities = [s for s in states if s.entity_id.startswith("sensor.")]
    assert len(qube_entities) > 0

    # Check if the data is stored
    assert entry.runtime_data is not None

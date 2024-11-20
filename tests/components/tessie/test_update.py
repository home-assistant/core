"""Test the Tessie update platform."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import assert_entities, setup_platform


async def test_updates(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that update entity is correct."""

    entry = await setup_platform(hass, [Platform.UPDATE])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    entity_id = "update.test_update"

    with patch(
        "homeassistant.components.tessie.update.schedule_software_update"
    ) as mock_update:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_update.assert_called_once()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_IN_PROGRESS) == 1

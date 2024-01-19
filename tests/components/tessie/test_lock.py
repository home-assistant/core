"""Test the Tessie lock platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_locks(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the lock entity is correct."""

    entry = await setup_platform(hass, [Platform.LOCK])

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )

    entity_id = "lock.test_lock"

    # Test lock set value functions
    with patch("homeassistant.components.tessie.lock.lock") as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_run.assert_called_once()
    assert hass.states.get(entity_id).state == STATE_LOCKED

    with patch("homeassistant.components.tessie.lock.unlock") as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )

        mock_run.assert_called_once()

    # Test charge cable lock set value functions
    entity_id = "lock.test_charge_cable_lock"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )

    with patch(
        "homeassistant.components.tessie.lock.open_unlock_charge_port"
    ) as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        assert hass.states.get(entity_id).state == STATE_UNLOCKED
        mock_run.assert_called_once()

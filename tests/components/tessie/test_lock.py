"""Test the Tessie lock platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import assert_entities, setup_platform


async def test_locks(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the lock entity is correct."""

    entry = await setup_platform(hass, [Platform.LOCK])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    # Test lock set value functions
    entity_id = "lock.test_lock"
    with patch("homeassistant.components.tessie.lock.lock") as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_run.assert_called_once()
    assert hass.states.get(entity_id).state == LockState.LOCKED

    with patch("homeassistant.components.tessie.lock.unlock") as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_run.assert_called_once()
    assert hass.states.get(entity_id).state == LockState.UNLOCKED

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
        assert hass.states.get(entity_id).state == LockState.UNLOCKED
        mock_run.assert_called_once()

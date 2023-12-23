"""Test the Tessie lock platform."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_locks(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Tests that the lock entity is correct."""

    assert len(hass.states.async_all("lock")) == 0

    await setup_platform(hass)

    assert hass.states.async_all("lock") == snapshot(name="all")

    entity_id = "lock.test"

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
    assert hass.states.get(entity_id).state == STATE_UNLOCKED

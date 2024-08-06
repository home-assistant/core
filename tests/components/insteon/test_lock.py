"""Tests for the Insteon lock."""

from unittest.mock import patch

import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon import (
    DOMAIN,
    insteon_entity,
    utils as insteon_utils,
)
from homeassistant.components.lock import (  # SERVICE_LOCK,; SERVICE_UNLOCK,
    DOMAIN as LOCK_DOMAIN,
)
from homeassistant.const import (  # ATTR_ENTITY_ID,;
    EVENT_HOMEASSISTANT_STOP,
    STATE_LOCKED,
    STATE_UNLOCKED,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

from tests.common import MockConfigEntry

devices = MockDevices()


@pytest.fixture(autouse=True)
def lock_platform_only():
    """Only setup the lock and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.insteon.INSTEON_PLATFORMS",
        (Platform.LOCK,),
    ):
        yield


@pytest.fixture(autouse=True)
def patch_setup_and_devices():
    """Patch the Insteon setup process and devices."""
    with (
        patch.object(insteon, "async_connect", new=mock_connection),
        patch.object(insteon, "async_close"),
        patch.object(insteon, "devices", devices),
        patch.object(insteon_utils, "devices", devices),
        patch.object(
            insteon_entity,
            "devices",
            devices,
        ),
    ):
        yield


async def mock_connection(*args, **kwargs):
    """Return a successful connection."""
    return True


async def test_lock_lock(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test locking an Insteon lock device."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    try:
        lock = entity_registry.async_get("lock.device_55_55_55_55_55_55")
        state = hass.states.get(lock.entity_id)
        assert state.state is STATE_UNLOCKED

        # lock via UI
        await hass.services.async_call(
            LOCK_DOMAIN, "lock", {"entity_id": lock.entity_id}, blocking=True
        )
        assert devices["55.55.55"].async_lock.call_count == 1
    finally:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()


async def test_lock_unlock(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test locking an Insteon lock device."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    devices["55.55.55"].groups[1].set_value(255)

    try:
        lock = entity_registry.async_get("lock.device_55_55_55_55_55_55")
        state = hass.states.get(lock.entity_id)

        assert state.state is STATE_LOCKED

        # lock via UI
        await hass.services.async_call(
            LOCK_DOMAIN, "unlock", {"entity_id": lock.entity_id}, blocking=True
        )
        assert devices["55.55.55"].async_unlock.call_count == 1
    finally:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

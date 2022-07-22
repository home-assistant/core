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
from homeassistant.const import (  # ATTR_ENTITY_ID,; STATE_LOCKED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNLOCKED,
    Platform,
)
from homeassistant.helpers import entity_registry as er

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

from tests.common import MockConfigEntry

# from homeassistant.helpers.entity_component import async_update_entity
# from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def lock_platform_only():
    """Only setup the lock and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.insteon.INSTEON_PLATFORMS",
        (Platform.LOCK,),
    ):
        yield


async def mock_connection(*args, **kwargs):
    """Return a successful connection."""
    return True


async def test_lock_lock(hass):
    """Test locking an Insteon lock device."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)
    registry_entity = er.async_get(hass)

    with patch.object(insteon, "async_connect", new=mock_connection), patch.object(
        insteon, "async_close"
    ), patch.object(insteon, "devices", MockDevices()) as devices, patch.object(
        insteon_utils, "devices", devices
    ), patch.object(
        insteon_entity, "devices", devices
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        try:
            lock = registry_entity.async_get("lock.device_55_55_55_55_55_55")
            state = hass.states.get(lock.entity_id)
            assert state.state is STATE_UNLOCKED

            print("Device method: ", devices["555555"].async_lock)
            # lock via UI
            await hass.services.async_call(
                LOCK_DOMAIN, "lock", {"entity_id": lock.entity_id}, blocking=True
            )
            assert devices["55.55.55"].async_lock.call_count == 1
        finally:
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()

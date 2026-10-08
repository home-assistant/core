"""Tests for the Insteon base entity."""

from unittest.mock import patch

import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon import (
    DOMAIN,
    entity as insteon_entity,
    utils as insteon_utils,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

from tests.common import MockConfigEntry

devices = MockDevices()

OLD_ENTITY_ID = "lock.device_55_55_55_55_55_55"
NEW_ENTITY_ID = "lock.renamed"


@pytest.fixture(autouse=True)
def lock_platform_only():
    """Only setup the lock platform to speed up tests."""
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
        patch.object(insteon_entity, "devices", devices),
    ):
        yield


async def mock_connection(*args, **kwargs):
    """Return a successful connection."""
    return True


@pytest.mark.parametrize(
    "service", ["load_all_link_database", "print_all_link_database"]
)
async def test_aldb_services_after_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service: str,
) -> None:
    """Test the ALDB services target the new entity_id after a rename."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry.async_update_entity(OLD_ENTITY_ID, new_entity_id=NEW_ENTITY_ID)
    await hass.async_block_till_done()

    try:
        with patch.object(insteon_entity, "print_aldb_to_log") as mock_print:
            await hass.services.async_call(
                DOMAIN, service, {"entity_id": OLD_ENTITY_ID}, blocking=True
            )
            await hass.async_block_till_done()
            mock_print.assert_not_called()

            await hass.services.async_call(
                DOMAIN, service, {"entity_id": NEW_ENTITY_ID}, blocking=True
            )
            await hass.async_block_till_done()
            mock_print.assert_called_once_with(devices["55.55.55"].aldb)
    finally:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

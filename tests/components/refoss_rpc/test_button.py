"""Tests for refoss_rpc button platform."""

from unittest.mock import Mock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.refoss_rpc.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import set_integration


async def test_rpc_button(
    hass: HomeAssistant, mock_rpc_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test  device  button."""
    await set_integration(hass)

    entity_id = "button.test_name_reboot"

    # reboot button
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC_reboot"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_rpc_device.trigger_reboot.call_count == 1


@pytest.mark.parametrize(
    ("old_unique_id", "new_unique_id", "migration"),
    [
        ("test_name_reboot", "123456789ABC_reboot", True),
        ("123456789ABC_reboot", "123456789ABC_reboot", False),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    old_unique_id: str,
    new_unique_id: str,
    migration: bool,
) -> None:
    """Test migration of unique_id."""
    entry = await set_integration(hass, skip_setup=True)

    entity = entity_registry.async_get_or_create(
        suggested_object_id="test_name_reboot",
        domain=BUTTON_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("button.test_name_reboot")
    assert entity_entry
    assert entity_entry.unique_id == new_unique_id

    assert (
        bool("Migrating unique_id for button.test_name_reboot" in caplog.text)
        == migration
    )

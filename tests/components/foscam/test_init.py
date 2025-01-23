"""Test the Foscam component."""

from unittest.mock import patch

from homeassistant.components.foscam import DOMAIN, config_flow
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_mock_foscam_camera
from .const import ENTRY_ID, VALID_CONFIG

from tests.common import MockConfigEntry


async def test_unique_id_new_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unique ID for a newly added device is correct."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID
    )
    entry.add_to_hass(hass)

    with (
        # Mock a valid camera instance"
        patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_camera,
    ):
        setup_mock_foscam_camera(mock_foscam_camera)
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    # Test that unique_id remains the same.
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{ENTRY_ID}_sleep_switch"
    )
    entity_new = entity_registry.async_get(entity_id)
    assert entity_new.unique_id == f"{ENTRY_ID}_sleep_switch"


async def test_switch_unique_id_migration_ok(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the unique ID for a sleep switch is migrated to the new format."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID, version=1
    )
    entry.add_to_hass(hass)

    entity_before = entity_registry.async_get_or_create(
        SWITCH_DOMAIN, DOMAIN, "sleep_switch", config_entry=entry
    )
    assert entity_before.unique_id == "sleep_switch"

    # Update config entry with version 2
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID, version=2
    )
    entry.add_to_hass(hass)

    with (
        # Mock a valid camera instance"
        patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_camera,
    ):
        setup_mock_foscam_camera(mock_foscam_camera)
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    entity_id_new = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{ENTRY_ID}_sleep_switch"
    )
    assert hass.states.get(entity_id_new)
    entity_after = entity_registry.async_get(entity_id_new)
    assert entity_after.previous_unique_id == "sleep_switch"
    assert entity_after.unique_id == f"{ENTRY_ID}_sleep_switch"


async def test_unique_id_migration_not_needed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the unique ID for a sleep switch is not executed if already in right format."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID
    )
    entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        SWITCH_DOMAIN, DOMAIN, f"{ENTRY_ID}_sleep_switch", config_entry=entry
    )

    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{ENTRY_ID}_sleep_switch"
    )
    entity_before = entity_registry.async_get(entity_id)
    assert entity_before.unique_id == f"{ENTRY_ID}_sleep_switch"

    with (
        # Mock a valid camera instance"
        patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_camera,
        patch(
            "homeassistant.components.foscam.async_migrate_entry",
            return_value=True,
        ),
    ):
        setup_mock_foscam_camera(mock_foscam_camera)
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    # Test that unique_id remains the same.
    assert hass.states.get(entity_id)
    entity_after = entity_registry.async_get(entity_id)
    assert entity_after.unique_id == entity_before.unique_id

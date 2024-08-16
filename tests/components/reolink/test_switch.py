"""Test the Reolink switch platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.reolink import const
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .conftest import TEST_UID

from tests.common import MockConfigEntry


async def test_cleanup_hdr_switch_(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cleanup of the HDR switch entity."""
    original_id = f"{TEST_UID}_hdr"
    domain = Platform.SWITCH

    reolink_connect.channels = [0]
    reolink_connect.supported.return_value = True

    entity_registry.async_get_or_create(
        domain=domain,
        platform=const.DOMAIN,
        unique_id=original_id,
        config_entry=config_entry,
        suggested_object_id=original_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert entity_registry.async_get_entity_id(domain, const.DOMAIN, original_id)

    # setup CH 0 and host entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [domain]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(domain, const.DOMAIN, original_id) is None
    )


async def test_hdr_switch_deprecated_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repairs issue is raised when hdr switch entity used."""
    original_id = f"{TEST_UID}_hdr"
    domain = Platform.SWITCH

    reolink_connect.channels = [0]
    reolink_connect.supported.return_value = True

    entity_registry.async_get_or_create(
        domain=domain,
        platform=const.DOMAIN,
        unique_id=original_id,
        config_entry=config_entry,
        suggested_object_id=original_id,
        disabled_by=None,
    )

    assert entity_registry.async_get_entity_id(domain, const.DOMAIN, original_id)

    # setup CH 0 and host entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [domain]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(domain, const.DOMAIN, original_id)

    assert (const.DOMAIN, "hdr_switch_deprecated") in issue_registry.issues

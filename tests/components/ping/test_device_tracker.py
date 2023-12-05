"""Test the binary sensor platform of ping."""
from unittest.mock import patch

import pytest

from homeassistant.components.device_tracker import legacy
from homeassistant.components.ping.const import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import dump

from tests.common import MockConfigEntry, patch_yaml_files


@pytest.mark.usefixtures("setup_integration")
async def test_setup_and_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test sensor setup and update."""

    entry = entity_registry.async_get("device_tracker.10_10_10_10")
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # check device tracker state is not there
    state = hass.states.get("device_tracker.10_10_10_10")
    assert state is None

    # enable the entity
    updated_entry = entity_registry.async_update_entity(
        entity_id="device_tracker.10_10_10_10", disabled_by=None
    )
    assert updated_entry != entry
    assert updated_entry.disabled is False

    # reload config entry to enable entity
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # check device tracker is now "home"
    state = hass.states.get("device_tracker.10_10_10_10")
    assert state.state == "home"


async def test_import_issue_creation(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
):
    """Test if import issue is raised."""

    await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": {"platform": "ping", "hosts": {"test": "10.10.10.10"}}},
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue


async def test_import_delete_known_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
):
    """Test if import deletes known devices."""
    yaml_devices = {
        "test": {
            "hide_if_away": True,
            "mac": "00:11:22:33:44:55",
            "name": "Test name",
            "picture": "/local/test.png",
            "track": True,
        },
    }
    files = {legacy.YAML_DEVICES: dump(yaml_devices)}

    with patch_yaml_files(files, True), patch(
        "homeassistant.components.ping.device_tracker.remove_device_from_config"
    ) as remove_device_from_config:
        await async_setup_component(
            hass,
            "device_tracker",
            {"device_tracker": {"platform": "ping", "hosts": {"test": "10.10.10.10"}}},
        )
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert len(remove_device_from_config.mock_calls) == 1

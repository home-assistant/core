"""Test the binary sensor platform of ping."""
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from icmplib import Host
import pytest

from homeassistant.components.ping.const import DOMAIN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration")
async def test_setup_and_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
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

    freezer.tick(timedelta(minutes=5))
    await hass.async_block_till_done()

    # check device tracker is still "home"
    state = hass.states.get("device_tracker.10_10_10_10")
    assert state.state == "home"

    # check if device tracker updates to "not home"
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        freezer.tick(timedelta(minutes=5))
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.10_10_10_10")
    assert state.state == "not_home"


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

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue

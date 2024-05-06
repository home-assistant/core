"""Test the binary sensor platform of ping."""
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from icmplib import Host
import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.ping.const import CONF_IMPORTED_BY, DOMAIN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration")
async def test_setup_and_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor setup and update."""

    # check if binary sensor is there
    entry = entity_registry.async_get("binary_sensor.10_10_10_10")
    assert entry == snapshot(exclude=props("unique_id"))

    state = hass.states.get("binary_sensor.10_10_10_10")
    assert state == snapshot

    # check if the sensor turns off.
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        freezer.tick(timedelta(minutes=6))
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.10_10_10_10")
    assert state == snapshot


async def test_disabled_after_import(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
):
    """Test if binary sensor is disabled after import."""
    config_entry.data = {CONF_IMPORTED_BY: "device_tracker"}
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # check if entity is disabled after import by device tracker
    entry = entity_registry.async_get("binary_sensor.10_10_10_10")
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_import_issue_creation(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
):
    """Test if import issue is raised."""

    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "ping",
                "name": "test",
                "host": "127.0.0.1",
                "count": 1,
            }
        },
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue

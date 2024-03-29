"""Tests for gree component."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gree.const import DOMAIN as GREE_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ENTITY_ID_WATER_FULL = f"{DOMAIN}.fake_device_1_water_full"


async def async_setup_gree(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the gree binary_sensor platform."""
    entry = MockConfigEntry(domain=GREE_DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, GREE_DOMAIN, {GREE_DOMAIN: {DOMAIN: {}}})
    await hass.async_block_till_done()
    return entry


@patch("homeassistant.components.gree.PLATFORMS", [DOMAIN])
async def test_registry_settings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for entity registry settings (disabled_by, unique_id)."""
    entry = await async_setup_gree(hass)

    state = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert state == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state(
    hass: HomeAssistant,
) -> None:
    """Test for reading state of entity."""
    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID_WATER_FULL)
    assert state is not None
    assert state.state == STATE_OFF

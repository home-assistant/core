"""Tests for the Nextcloud init."""

from copy import deepcopy
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import init_integration
from .const import NC_DATA, VALID_CONFIG


async def test_setup_entity_without_update(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test update entity is created w/o available update."""
    with patch("homeassistant.components.nextcloud.PLATFORMS", [Platform.UPDATE]):
        entry = await init_integration(hass, VALID_CONFIG, NC_DATA)

    assert entry.state == ConfigEntryState.LOADED

    states = hass.states.async_all()
    assert len(states) == 1
    assert states[0].state == snapshot(name=f"{states[0].entity_id}_state")
    assert states[0].attributes == snapshot(name=f"{states[0].entity_id}_attributes")


async def test_setup_entity_with_update(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test update entity is created with available update."""
    data = deepcopy(NC_DATA)
    data["nextcloud"]["system"]["update"]["available"] = True
    data["nextcloud"]["system"]["update"]["available_version"] = "30.0.0.0"
    with patch("homeassistant.components.nextcloud.PLATFORMS", [Platform.UPDATE]):
        entry = await init_integration(hass, VALID_CONFIG, data)

    assert entry.state == ConfigEntryState.LOADED

    states = hass.states.async_all()
    assert len(states) == 1
    assert states[0].state == snapshot(name=f"{states[0].entity_id}_state")
    assert states[0].attributes == snapshot(name=f"{states[0].entity_id}_attributes")


async def test_setup_no_entity(hass: HomeAssistant) -> None:
    """Test no update entity is created, when no data available."""
    data = deepcopy(NC_DATA)
    data["nextcloud"]["system"].pop("update")  # only nc<28.0.0
    with patch("homeassistant.components.nextcloud.PLATFORMS", [Platform.UPDATE]):
        entry = await init_integration(hass, VALID_CONFIG, data)

    assert entry.state == ConfigEntryState.LOADED

    states = hass.states.async_all()
    assert len(states) == 0

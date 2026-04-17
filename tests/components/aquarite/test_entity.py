"""Tests for the Aquarite base entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.components.aquarite.const import BRAND, DOMAIN, MODEL
from homeassistant.components.aquarite.entity import AquariteEntity

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME


def _make_coordinator(version: Any = 825) -> MagicMock:
    """Build a mock coordinator with pool_id, pool_name, and version."""
    coord = MagicMock()
    coord.pool_id = MOCK_POOL_ID
    coord.pool_name = MOCK_POOL_NAME
    coord.get_value = MagicMock(return_value=version)
    return coord


def _patch_init():
    """Patch CoordinatorEntity.__init__ to skip hass wiring."""
    return patch(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, coordinator, context=None: setattr(
            self, "coordinator", coordinator
        ),
    )


def test_entity_device_info_with_version() -> None:
    """Test device_info includes sw_version when available."""
    coord = _make_coordinator(version=825)
    with _patch_init():
        entity = AquariteEntity(coord)

    info = entity._attr_device_info
    assert info["identifiers"] == {(DOMAIN, MOCK_POOL_ID)}
    assert info["name"] == MOCK_POOL_NAME
    assert info["manufacturer"] == BRAND
    assert info["model"] == MODEL
    assert info["sw_version"] == "825"


def test_entity_device_info_without_version() -> None:
    """Test device_info handles missing sw_version (None)."""
    coord = _make_coordinator(version=None)
    with _patch_init():
        entity = AquariteEntity(coord)

    assert entity._attr_device_info["sw_version"] is None


def test_entity_device_info_with_zero_version() -> None:
    """Test device_info preserves a falsy but valid version (e.g., 0)."""
    coord = _make_coordinator(version=0)
    with _patch_init():
        entity = AquariteEntity(coord)

    assert entity._attr_device_info["sw_version"] == "0"


def test_entity_pool_id_property() -> None:
    """Test the pool_id property derives from coordinator."""
    coord = _make_coordinator()
    with _patch_init():
        entity = AquariteEntity(coord)
    assert entity.pool_id == MOCK_POOL_ID


def test_entity_pool_name_property() -> None:
    """Test the pool_name property derives from coordinator."""
    coord = _make_coordinator()
    with _patch_init():
        entity = AquariteEntity(coord)
    assert entity.pool_name == MOCK_POOL_NAME


def test_entity_build_unique_id() -> None:
    """Test build_unique_id concatenates pool_id and suffix."""
    coord = _make_coordinator()
    with _patch_init():
        entity = AquariteEntity(coord)
    assert entity.build_unique_id("temperature") == f"{MOCK_POOL_ID}-temperature"

"""Tests for recorder storage module."""

from __future__ import annotations

import pytest

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.storage import RecorderExclusionsStore
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import async_recorder_block_till_done


@pytest.mark.usefixtures("recorder_mock")
async def test_exclusions_store_load_empty(hass: HomeAssistant) -> None:
    """Test loading empty exclusions store."""
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    instance = get_instance(hass)
    assert instance.exclusions_store is not None
    assert instance.exclusions_store.excluded_entities == set()


@pytest.mark.usefixtures("recorder_mock")
async def test_exclusions_store_add_remove(hass: HomeAssistant) -> None:
    """Test adding and removing exclusions."""
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    instance = get_instance(hass)
    store = instance.exclusions_store
    assert store is not None

    # Add exclusion
    assert store.add_exclusion("sensor.test1") is True
    assert "sensor.test1" in store.excluded_entities

    # Add duplicate (should return False)
    assert store.add_exclusion("sensor.test1") is False

    # Add another
    assert store.add_exclusion("sensor.test2") is True
    assert len(store.excluded_entities) == 2

    # Remove exclusion
    assert store.remove_exclusion("sensor.test1") is True
    assert "sensor.test1" not in store.excluded_entities

    # Remove non-existent (should return False)
    assert store.remove_exclusion("sensor.test1") is False


@pytest.mark.usefixtures("recorder_mock")
async def test_exclusions_store_is_excluded(hass: HomeAssistant) -> None:
    """Test is_excluded method."""
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    instance = get_instance(hass)
    store = instance.exclusions_store
    assert store is not None

    assert store.is_excluded("sensor.test1") is False
    store.add_exclusion("sensor.test1")
    assert store.is_excluded("sensor.test1") is True


@pytest.mark.usefixtures("recorder_mock")
async def test_exclusions_store_persistence(hass: HomeAssistant) -> None:
    """Test saving and loading exclusions."""
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    instance = get_instance(hass)
    store = instance.exclusions_store
    assert store is not None

    # Add exclusions
    store.add_exclusion("sensor.test1")
    store.add_exclusion("sensor.test2")

    # Save
    await store.async_save()

    # Create a new store and load
    new_store = RecorderExclusionsStore(hass)
    await new_store.async_load()

    assert new_store.excluded_entities == {"sensor.test1", "sensor.test2"}


@pytest.mark.usefixtures("recorder_mock")
async def test_exclusions_store_get_exclusions_data(hass: HomeAssistant) -> None:
    """Test get_exclusions_data method."""
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    instance = get_instance(hass)
    store = instance.exclusions_store
    assert store is not None

    store.add_exclusion("sensor.storage_excluded")
    store.add_exclusion("sensor.another_excluded")

    # Test storage exclusions
    result = store.get_exclusions_data()
    assert result["sensor.storage_excluded"] == "storage"
    assert result["sensor.another_excluded"] == "storage"

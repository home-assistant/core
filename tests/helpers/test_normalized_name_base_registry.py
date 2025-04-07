"""Tests for the normalized name base registry helper."""

import pytest

from homeassistant.helpers.normalized_name_base_registry import (
    NormalizedNameBaseRegistryEntry,
    NormalizedNameBaseRegistryItems,
    normalize_name,
)


@pytest.fixture
def registry_items() -> NormalizedNameBaseRegistryItems:
    """Fixture for registry items."""
    return NormalizedNameBaseRegistryItems[NormalizedNameBaseRegistryEntry]()


def test_normalize_name() -> None:
    """Test normalize_name."""
    assert normalize_name("Hello World") == "helloworld"
    assert normalize_name("HELLO WORLD") == "helloworld"
    assert normalize_name("  Hello   World  ") == "helloworld"


def test_registry_items(
    registry_items: NormalizedNameBaseRegistryItems[NormalizedNameBaseRegistryEntry],
) -> None:
    """Test registry items."""
    entry = NormalizedNameBaseRegistryEntry(name="Hello World")
    registry_items["key"] = entry
    assert registry_items["key"] == entry
    assert list(registry_items.values()) == [entry]
    assert registry_items.get_by_name("Hello World") == entry

    # test update entry
    entry2 = NormalizedNameBaseRegistryEntry(name="Hello World 2")
    registry_items["key"] = entry2
    assert registry_items["key"] == entry2
    assert list(registry_items.values()) == [entry2]
    assert registry_items.get_by_name("Hello World 2") == entry2

    # test delete entry
    del registry_items["key"]
    assert "key" not in registry_items
    assert not registry_items.values()


def test_key_already_in_use(
    registry_items: NormalizedNameBaseRegistryItems[NormalizedNameBaseRegistryEntry],
) -> None:
    """Test key already in use."""
    entry = NormalizedNameBaseRegistryEntry(name="Hello World")
    registry_items["key"] = entry

    # should raise ValueError if we update a
    # key with a entry with the same normalized name
    entry = NormalizedNameBaseRegistryEntry(name="Hello World 2")
    registry_items["key2"] = entry
    with pytest.raises(ValueError):
        registry_items["key"] = entry

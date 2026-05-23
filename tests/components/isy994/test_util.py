"""Tests for ISY994 util functions."""

from unittest.mock import MagicMock

from homeassistant.components.isy994.models import IsyData
from homeassistant.components.isy994.util import _async_cleanup_registry_entries
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


def _make_isy_data(uuid: str = "test-uuid") -> IsyData:
    """Return a minimal IsyData with a mocked root ISY."""
    data = IsyData.__new__(IsyData)
    IsyData.__init__(data)
    data.root = MagicMock()
    data.root.uuid = uuid
    return data


async def test_cleanup_removes_stale_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Stale entities not present in isy_data.unique_ids are removed."""
    entry = MockConfigEntry(domain="isy994")
    entry.add_to_hass(hass)

    isy_data = _make_isy_data()
    node = MagicMock()
    node.address = "1 1"
    node.protocol = "insteon"
    isy_data.nodes[Platform.SENSOR].append(node)
    entry.runtime_data = isy_data

    current = entity_registry.async_get_or_create(
        "sensor", "isy994", "test-uuid_1 1", config_entry=entry
    )
    stale = entity_registry.async_get_or_create(
        "sensor", "isy994", "test-uuid_stale", config_entry=entry
    )

    _async_cleanup_registry_entries(hass, entry)

    assert entity_registry.async_is_registered(current.entity_id)
    assert not entity_registry.async_is_registered(stale.entity_id)


async def test_cleanup_no_extra_entities_is_noop(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: object,
) -> None:
    """When all registered entities are in unique_ids, nothing is removed."""
    entry = MockConfigEntry(domain="isy994")
    entry.add_to_hass(hass)

    isy_data = _make_isy_data()
    node = MagicMock()
    node.address = "2 2"
    node.protocol = "insteon"
    isy_data.nodes[Platform.SENSOR].append(node)
    entry.runtime_data = isy_data

    kept = entity_registry.async_get_or_create(
        "sensor", "isy994", "test-uuid_2 2", config_entry=entry
    )

    _async_cleanup_registry_entries(hass, entry)

    assert entity_registry.async_is_registered(kept.entity_id)


async def test_cleanup_removes_multiple_stale_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Multiple stale entities are all removed."""
    entry = MockConfigEntry(domain="isy994")
    entry.add_to_hass(hass)

    isy_data = _make_isy_data()
    entry.runtime_data = isy_data

    stale1 = entity_registry.async_get_or_create(
        "sensor", "isy994", "test-uuid_gone1", config_entry=entry
    )
    stale2 = entity_registry.async_get_or_create(
        "sensor", "isy994", "test-uuid_gone2", config_entry=entry
    )
    stale3 = entity_registry.async_get_or_create(
        "switch", "isy994", "test-uuid_gone3", config_entry=entry
    )

    _async_cleanup_registry_entries(hass, entry)

    assert not entity_registry.async_is_registered(stale1.entity_id)
    assert not entity_registry.async_is_registered(stale2.entity_id)
    assert not entity_registry.async_is_registered(stale3.entity_id)


async def test_cleanup_empty_registry_is_noop(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """With no registry entries, cleanup is a no-op."""
    entry = MockConfigEntry(domain="isy994")
    entry.add_to_hass(hass)

    isy_data = _make_isy_data()
    entry.runtime_data = isy_data

    _async_cleanup_registry_entries(hass, entry)

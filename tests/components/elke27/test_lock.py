"""Tests for Elke27 locks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.elke27 import lock as lock_module
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.lock import async_setup_entry
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.is_ready = True
        self.panel_name = None
        self.async_set_lock = AsyncMock(return_value=True)


async def test_lock_entities_updates_and_actions(hass: HomeAssistant) -> None:
    """Test lock entities are created, update, and delegate actions."""
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.60"})
    entry.add_to_hass(hass)

    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
        ),
        locks=[
            SimpleNamespace(lock_id=1, name="Front Door", locked=False),
            SimpleNamespace(lock_id=2, name="Garage Door", locked=True),
        ],
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[lock_module.Elke27Lock] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 2

    lock_1 = next(entity for entity in entities if entity._lock_id == 1)
    await lock_1.async_lock()
    hub.async_set_lock.assert_awaited_once_with(1, locked=True)

    snapshot.locks[0].locked = True
    coordinator.async_set_updated_data(snapshot)
    await hass.async_block_till_done()
    assert lock_1.is_locked is True


async def test_lock_pin_required(hass: HomeAssistant) -> None:
    """Test PIN-required error surfaces as HomeAssistantError."""
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.61"})
    entry.add_to_hass(hass)

    hub = _Hub()
    hub.async_set_lock.side_effect = lock_module.Elke27PinRequiredError

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
        ),
        locks=[SimpleNamespace(lock_id=1, name="Front Door", locked=False)],
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[lock_module.Elke27Lock] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 1

    lock_1 = entities[0]
    with pytest.raises(
        HomeAssistantError, match="PIN required to perform this action."
    ):
        await lock_1.async_unlock()


async def test_lock_setup_edge_cases(hass: HomeAssistant) -> None:
    """Verify setup handles missing runtime data and snapshots."""
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.62"})
    entry.add_to_hass(hass)
    entry.runtime_data = None

    entities: list[lock_module.Elke27Lock] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    coordinator.async_set_updated_data(None)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

    snapshot = SimpleNamespace(locks=[])
    coordinator.async_set_updated_data(snapshot)
    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

    snapshot.locks = [SimpleNamespace(lock_id="x", name="Bad")]
    coordinator.async_set_updated_data(snapshot)
    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []


def test_lock_properties_when_missing() -> None:
    """Verify properties handle missing lock data."""
    hub = _Hub()
    coordinator = SimpleNamespace(data=None)
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.63"})
    lock = lock_module.Elke27Lock(coordinator, hub, entry, 1, SimpleNamespace())
    assert lock.is_locked is None
    hub.is_ready = False
    assert lock.available is False
    assert lock.is_locked is None


def test_lock_iter_variants() -> None:
    """Verify lock iteration for mapping and list."""
    assert list(lock_module._iter_locks({"locks": {1: "x"}})) == []
    snapshot = SimpleNamespace(locks={1: "x"})
    assert list(lock_module._iter_locks(snapshot)) == ["x"]
    snapshot.locks = ["a"]
    assert list(lock_module._iter_locks(snapshot)) == ["a"]
    snapshot.locks = "bad"
    assert list(lock_module._iter_locks(snapshot)) == []

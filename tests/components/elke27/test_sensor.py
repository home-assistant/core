"""Tests for Elke27 sensors."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.components.elke27.sensor import async_setup_entry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.is_ready = True
        self.panel_name = None


async def test_sensor_updates_from_coordinator(hass: HomeAssistant) -> None:
    """Test sensors reflect coordinator snapshot updates."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.60"})
    entry.add_to_hass(hass)

    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
        )
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)

    assert len(entities) == 2
    values = {entity.native_value for entity in entities}
    assert {"Panel A", "connected"} == values

    snapshot.panel_info.name = "Panel B"
    hub.is_ready = False
    coordinator.async_set_updated_data(snapshot)
    await hass.async_block_till_done()

    values = {entity.native_value for entity in entities}
    assert {"Panel B", "disconnected"} == values


async def test_sensor_setup_missing_runtime(hass: HomeAssistant) -> None:
    """Verify setup returns when runtime data is missing."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.61"})
    entry.add_to_hass(hass)
    entities: list[Any] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

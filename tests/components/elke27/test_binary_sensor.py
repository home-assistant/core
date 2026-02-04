"""Tests for Elke27 binary sensor setup."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.components.elke27.binary_sensor import async_setup_entry
from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self, *, ready: bool = True) -> None:
        self._ready = ready
        self.panel_name = None

    @property
    def is_ready(self) -> bool:
        return self._ready

    def subscribe_typed(self, callback: Any) -> Any:
        def _unsub() -> None:
            return None

        return _unsub

    def get_snapshot(self) -> Any:
        return None

    def __getattr__(self, name: str) -> Any:
        if name == "client":
            raise AssertionError("hub.client should not be accessed")
        raise AttributeError(name)


async def test_binary_sensor_uses_zone_definitions(hass: HomeAssistant) -> None:
    """Verify zone definitions drive setup without hub.client usage."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.1"})
    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel=SimpleNamespace(
            name="Panel",
            mac="00:11:22:33:44:55",
            serial="123",
            model="X",
            firmware="1",
        ),
        zones={
            1: SimpleNamespace(zone_id=1, name="Zone A", open=False),
            2: SimpleNamespace(zone_id=2, name="Zone B", open=False),
        },
        zone_definitions={
            1: SimpleNamespace(zone_id=1, name="Zone A", definition="UNDEFINED"),
            2: SimpleNamespace(zone_id=2, name="Zone B", definition="BURG PERIM INST", zone_type="door"),
        },
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[Any] = []

    def _add_entities(new_entities: list[Any]) -> None:
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)

    assert len(entities) == 1
    assert entities[0]._attr_name == "Zone B"

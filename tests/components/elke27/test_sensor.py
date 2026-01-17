"""Tests for Elke27 sensors."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components.elke27.const import DATA_COORDINATOR, DATA_HUB, DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
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
    hass.data[DOMAIN] = {
        entry.entry_id: {DATA_HUB: hub, DATA_COORDINATOR: coordinator}
    }

    entities = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)

    states = hass.states.async_all("sensor")
    assert len(states) == 2
    assert {"Panel A", "connected"} == {state.state for state in states}

    snapshot.panel_info.name = "Panel B"
    hub.is_ready = False
    coordinator.async_set_updated_data(snapshot)
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert {"Panel B", "disconnected"} == {state.state for state in states}

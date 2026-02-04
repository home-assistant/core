"""Tests for Elke27 output switches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.elke27 import switch as switch_module
from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.components.elke27.switch import async_setup_entry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.is_ready = True
        self.panel_name = None
        self.async_set_output = AsyncMock(return_value=True)
        self.async_set_zone_bypass = AsyncMock(return_value=True)


async def test_output_entities_updates_and_actions(hass: HomeAssistant) -> None:
    """Test output entities are created, update, and delegate actions."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.60"})
    entry.add_to_hass(hass)

    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
        ),
        outputs=[
            SimpleNamespace(output_id=1, name="Output 1", state=False),
            SimpleNamespace(output_id=2, name="Output 2", state=True),
        ],
        zones=[],
        zone_definitions={},
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[switch_module.Elke27OutputSwitch] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 2

    unique_ids = {entity.unique_id for entity in entities}
    assert unique_ids == {"aa:bb:cc:dd:ee:ff:output:1", "aa:bb:cc:dd:ee:ff:output:2"}

    output_1 = next(entity for entity in entities if entity._output_id == 1)

    await output_1.async_turn_on()
    hub.async_set_output.assert_awaited_once_with(1, True)
    assert snapshot.outputs[0].state is False

    snapshot.outputs[0].state = True
    coordinator.async_set_updated_data(snapshot)
    await hass.async_block_till_done()

    assert output_1.is_on is True


async def test_output_pin_required(hass: HomeAssistant) -> None:
    """Test PIN-required error surfaces as HomeAssistantError."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.61"})
    entry.add_to_hass(hass)

    hub = _Hub()
    hub.async_set_output.side_effect = switch_module.Elke27PinRequiredError

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
        ),
        outputs=[SimpleNamespace(output_id=1, name="Output 1", state=False)],
        zones=[],
        zone_definitions={},
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[switch_module.Elke27OutputSwitch] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 1

    output_1 = next(entity for entity in entities if entity._output_id == 1)

    with pytest.raises(
        HomeAssistantError, match="PIN required to perform this action."
    ):
        await output_1.async_turn_on()


async def test_switch_setup_edge_cases(hass: HomeAssistant) -> None:
    """Verify setup handles missing runtime data and snapshots."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.62"})
    entry.add_to_hass(hass)
    entry.runtime_data = None

    entities: list[switch_module.Elke27OutputSwitch] = []

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

    snapshot = SimpleNamespace(outputs=[])
    coordinator.async_set_updated_data(snapshot)
    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

    snapshot.outputs = [SimpleNamespace(output_id="x", name="Bad")]
    coordinator.async_set_updated_data(snapshot)
    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []


def test_switch_properties_when_missing() -> None:
    """Verify properties handle missing output data."""
    hub = _Hub()
    coordinator = SimpleNamespace(data=None)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.63"})
    output = switch_module.Elke27OutputSwitch(
        coordinator, hub, entry, 1, SimpleNamespace()
    )
    assert output.is_on is None
    hub.is_ready = False
    assert output.available is False
    assert output.is_on is None


async def test_switch_turn_off_pin_required(hass: HomeAssistant) -> None:
    """Verify turn_off handles PIN required."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.64"})
    entry.add_to_hass(hass)
    hub = _Hub()
    hub.async_set_output.side_effect = switch_module.Elke27PinRequiredError
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    coordinator.async_set_updated_data(SimpleNamespace(outputs=[SimpleNamespace(output_id=1, state=True)]))
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    output = switch_module.Elke27OutputSwitch(
        coordinator, hub, entry, 1, SimpleNamespace(output_id=1)
    )
    with pytest.raises(
        HomeAssistantError, match="PIN required to perform this action."
    ):
        await output.async_turn_off()


def test_switch_iter_outputs_variants() -> None:
    """Verify output iteration for mapping and list."""
    snapshot = SimpleNamespace(outputs={1: "x"})
    assert list(switch_module._iter_outputs(snapshot)) == ["x"]
    snapshot.outputs = ["a"]
    assert list(switch_module._iter_outputs(snapshot)) == ["a"]

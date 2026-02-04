"""Tests for Elke27 output lights."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.elke27 import light as light_module
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.light import async_setup_entry
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.is_ready = True
        self.panel_name = None
        self.async_set_output = AsyncMock(return_value=True)


async def test_light_entities_updates_and_actions(hass: HomeAssistant) -> None:
    """Test light entities are created, update, and delegate actions."""
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
        outputs=[
            SimpleNamespace(output_id=1, name="Output 1", state=False),
            SimpleNamespace(output_id=2, name="Output 2", state=True),
        ],
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[light_module.Elke27OutputLight] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 2

    light_1 = next(entity for entity in entities if entity._output_id == 1)
    await light_1.async_turn_on()
    hub.async_set_output.assert_awaited_once_with(1, True)

    snapshot.outputs[0].state = True
    coordinator.async_set_updated_data(snapshot)
    await hass.async_block_till_done()
    assert light_1.is_on is True


async def test_light_pin_required(hass: HomeAssistant) -> None:
    """Test PIN-required error surfaces as HomeAssistantError."""
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.61"})
    entry.add_to_hass(hass)

    hub = _Hub()
    hub.async_set_output.side_effect = light_module.Elke27PinRequiredError

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
        ),
        outputs=[SimpleNamespace(output_id=1, name="Output 1", state=False)],
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[light_module.Elke27OutputLight] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 1

    light_1 = next(entity for entity in entities if entity._output_id == 1)
    with pytest.raises(HomeAssistantError, match="PIN required to perform this action."):
        await light_1.async_turn_on()

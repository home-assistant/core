"""Tests for Elke27 alarm control panel areas."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from elke27_lib import ArmMode

from homeassistant.components.elke27 import alarm_control_panel as alarm_module
from homeassistant.components.elke27.alarm_control_panel import async_setup_entry
from homeassistant.components.elke27.const import DATA_COORDINATOR, DATA_HUB, DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.is_ready = True
        self.panel_name = None
        self.async_arm_area = AsyncMock()
        self.async_disarm_area = AsyncMock()


async def test_area_entities_and_updates(hass: HomeAssistant) -> None:
    """Test area entities are created and update from snapshots."""
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
        areas=[
            SimpleNamespace(
                area_id=1,
                name="Area 1",
                arm_mode=None,
                alarm_active=False,
                ready=True,
                trouble=False,
            ),
            SimpleNamespace(
                area_id=2,
                name="Area 2",
                arm_mode=ArmMode.ARMED_AWAY,
                alarm_active=False,
            ),
        ],
    )
    coordinator.async_set_updated_data(snapshot)
    hass.data[DOMAIN] = {
        entry.entry_id: {DATA_HUB: hub, DATA_COORDINATOR: coordinator}
    }

    entities: list[alarm_module.Elke27AreaAlarmControlPanel] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 2

    unique_ids = {entity.unique_id for entity in entities}
    assert unique_ids == {"aa:bb:cc:dd:ee:ff:area:1", "aa:bb:cc:dd:ee:ff:area:2"}

    area_1 = next(entity for entity in entities if entity._area_id == 1)
    area_2 = next(entity for entity in entities if entity._area_id == 2)

    assert area_1.state == "disarmed"
    assert area_2.state == "armed_away"

    snapshot.areas[0].arm_mode = ArmMode.ARMED_STAY
    coordinator.async_set_updated_data(snapshot)
    await hass.async_block_till_done()

    assert area_1.state == "armed_home"


async def test_area_actions_and_pin_required(hass: HomeAssistant) -> None:
    """Test area action methods and PIN-required handling."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.61"})
    entry.add_to_hass(hass)

    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
        ),
        areas=[
            SimpleNamespace(
                area_id=1,
                name="Area 1",
                arm_mode=None,
                alarm_active=False,
            )
        ],
    )
    coordinator.async_set_updated_data(snapshot)
    hass.data[DOMAIN] = {
        entry.entry_id: {DATA_HUB: hub, DATA_COORDINATOR: coordinator}
    }

    entities: list[alarm_module.Elke27AreaAlarmControlPanel] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 1

    area_1 = next(entity for entity in entities if entity._area_id == 1)

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_away",
        {"entity_id": area_1.entity_id, "code": "1234"},
        blocking=True,
    )
    hub.async_arm_area.assert_awaited_once_with(1, alarm_module.ArmMode.ARMED_AWAY, "1234")

    hub.async_disarm_area.reset_mock()
    hub.async_disarm_area.side_effect = alarm_module.Elke27PinRequiredError
    with pytest.raises(HomeAssistantError, match="PIN required to perform this action."):
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_disarm",
            {"entity_id": area_1.entity_id},
            blocking=True,
        )

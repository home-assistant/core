"""Tests for Elke27 alarm control panel areas."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from elke27_lib import ArmMode
import pytest

from homeassistant.components.elke27 import alarm_control_panel as alarm_module
from homeassistant.components.elke27.alarm_control_panel import async_setup_entry
from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.models import Elke27RuntimeData
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
        self.async_set_zone_bypass = AsyncMock()


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
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

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
        zones=[
            SimpleNamespace(
                zone_id=1,
                name="Front Door",
                open=True,
                bypassed=False,
            ),
            SimpleNamespace(
                zone_id=2,
                name="Window",
                open=False,
                bypassed=False,
            ),
            SimpleNamespace(
                zone_id=3,
                name="Garage",
                open=True,
                bypassed=True,
            ),
        ],
        zone_definitions={},
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[alarm_module.Elke27AreaAlarmControlPanel] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 1

    area_1 = next(entity for entity in entities if entity._area_id == 1)

    await area_1.async_alarm_arm_away(code="1234")
    hub.async_arm_area.assert_awaited_once_with(1, alarm_module.ArmMode.ARMED_AWAY, "1234")

    hub.async_arm_area.reset_mock()
    hub.async_set_zone_bypass.reset_mock()
    await area_1.async_alarm_arm_custom_bypass(code="1234")
    hub.async_set_zone_bypass.assert_awaited_once_with(1, True, pin="1234")
    hub.async_arm_area.assert_awaited_once_with(
        1,
        alarm_module.ArmMode.ARMED_AWAY,
        "1234",
    )

    hub.async_disarm_area.reset_mock()
    hub.async_disarm_area.side_effect = alarm_module.Elke27PinRequiredError
    with pytest.raises(HomeAssistantError, match="PIN required to perform this action."):
        await area_1.async_alarm_disarm()


def test_area_state_and_ready_status_helpers() -> None:
    """Verify state mapping and ready status display helpers."""
    assert alarm_module._area_state_to_ha(SimpleNamespace(alarm_active=True)) == "triggered"
    assert alarm_module._area_state_to_ha(SimpleNamespace(arm_mode="disarmed")) == "disarmed"
    assert alarm_module._area_state_to_ha(SimpleNamespace(arm_mode="armed stay")) == "armed_home"
    assert alarm_module._area_state_to_ha(SimpleNamespace(arm_mode="armed night")) == "armed_night"
    assert alarm_module._area_state_to_ha(SimpleNamespace(arm_mode="armed away")) == "armed_away"
    assert alarm_module._area_state_to_ha(SimpleNamespace(arm_mode="bypass")) == "armed_custom_bypass"
    assert alarm_module._ready_status_display(SimpleNamespace(ready_status="RDY_AWAY")) == "Ready away"
    assert alarm_module._ready_status_display(SimpleNamespace(ready_status="RDY_STAY")) == "Ready stay"
    assert alarm_module._ready_status_display(SimpleNamespace(ready_status="RDY_NOT")) == "Not ready"


async def test_area_setup_skips_when_runtime_missing(hass: HomeAssistant) -> None:
    """Verify setup returns when runtime data is missing."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.80"})
    entry.add_to_hass(hass)

    entities: list[alarm_module.Elke27AreaAlarmControlPanel] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert not entities


def test_faulted_zones_helpers() -> None:
    """Verify faulted zone extraction and naming."""
    snapshot = SimpleNamespace(
        zones=[
            SimpleNamespace(zone_id=1, name="Door", open=True, bypassed=False),
            SimpleNamespace(zone_id=2, name="Window", open=False, bypassed=False),
            SimpleNamespace(zone_id=3, name="Garage", open=True, bypassed=True),
        ],
        zone_definitions={1: SimpleNamespace(name="Front Door")},
    )
    zones = alarm_module._faulted_zones(snapshot)
    assert zones == [(1, "Front Door")]

    assert alarm_module._zone_display_name(SimpleNamespace(zone_id=4, name=None), {}) == "Zone 4"


def test_normalize_code() -> None:
    """Verify code normalization."""
    assert alarm_module._normalize_code(None) is None
    with pytest.raises(HomeAssistantError):
        alarm_module._normalize_code("12ab")


def test_area_iter_helpers() -> None:
    """Verify area iter helpers handle mappings and lists."""
    snapshot = SimpleNamespace(areas={1: SimpleNamespace(area_id=1)})
    assert len(list(alarm_module._iter_areas(snapshot))) == 1
    assert alarm_module._get_area(snapshot, 1) is not None
    assert alarm_module._get_area(snapshot, 2) is None
    snapshot.areas = [SimpleNamespace(area_id=2)]
    assert alarm_module._get_area(snapshot, 2) is not None


async def test_area_properties_when_missing(hass: HomeAssistant) -> None:
    """Verify properties handle missing area data."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.90"})
    entry.add_to_hass(hass)
    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    coordinator.async_set_updated_data(SimpleNamespace(areas=[]))
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[alarm_module.Elke27AreaAlarmControlPanel] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert not entities

    area = alarm_module.Elke27AreaAlarmControlPanel(coordinator, hub, entry, 1, SimpleNamespace(area_id=1))
    assert area.state is None
    assert area.extra_state_attributes["ready"] is None
    hub.is_ready = False
    assert area.available is False

    snapshot = SimpleNamespace(
        areas=[SimpleNamespace(area_id=1, ready=True, trouble=False, ready_status="RDY_AWAY")],
        zones=[SimpleNamespace(zone_id=1, name="Door", open=True, bypassed=False)],
        zone_definitions={},
    )
    coordinator.async_set_updated_data(snapshot)
    assert area.extra_state_attributes["ready_status_display"] == "Ready away"

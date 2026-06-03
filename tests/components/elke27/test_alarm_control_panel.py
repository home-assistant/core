"""Tests for Elke27 alarm control panel areas."""

from unittest.mock import AsyncMock

from elke27_lib import (
    AreaState,
    ArmMode,
    PanelInfo,
    PanelSnapshot,
    TableInfo,
    ZoneState,
)
from elke27_lib.errors import Elke27PinRequiredError
import pytest

from homeassistant.components.elke27 import alarm_control_panel as alarm_module
from homeassistant.components.elke27.const import DOMAIN
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.is_ready = True
        self.panel_name = None
        self.async_arm_area = AsyncMock()
        self.async_disarm_area = AsyncMock()
        self.async_set_zone_bypass = AsyncMock(return_value=True)


def _snapshot(
    *,
    areas: dict[int, AreaState] | None = None,
    zones: dict[int, ZoneState] | None = None,
) -> PanelSnapshot:
    return PanelSnapshot(
        panel=PanelInfo(serial="1234"),
        table_info=TableInfo(),
        areas=areas or {},
        zones=zones or {},
        zone_definitions={},
        outputs={},
        output_definitions={},
        lights={},
        barriers={},
        locks={},
        thermostats={},
        version=1,
        updated_at=dt_util.utcnow(),
    )


def _setup_area_entities(
    hass: HomeAssistant,
    snapshot: PanelSnapshot,
) -> tuple[_Hub, list[alarm_module.Elke27AreaAlarmControlPanel]]:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.60", CONF_CLIENT_ID: "entryclientid"},
    )
    entry.add_to_hass(hass)
    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    coordinator.async_set_updated_data(snapshot)
    entities = [
        alarm_module.Elke27AreaAlarmControlPanel(coordinator, hub, entry, area)
        for area in snapshot.areas.values()
    ]
    return hub, entities


async def test_area_entities_and_updates(hass: HomeAssistant) -> None:
    """Test area entities are created and update from snapshots."""
    hub, entities = _setup_area_entities(
        hass,
        _snapshot(
            areas={
                1: AreaState(area_id=1, name="Area 1"),
                2: AreaState(area_id=2, name="Area 2", arm_mode=ArmMode.ARMED_AWAY),
            }
        ),
    )
    del hub

    assert len(entities) == 2
    assert {entity.unique_id for entity in entities} == {
        "entryclientid:1",
        "entryclientid:2",
    }
    area_1 = next(entity for entity in entities if entity._area_id == 1)
    area_2 = next(entity for entity in entities if entity._area_id == 2)

    assert area_1.device_info == {
        "identifiers": {(DOMAIN, "entryclientid:area:1")},
        "name": "Area 1",
        "via_device": (DOMAIN, "entryclientid"),
    }
    assert area_1.name is None
    assert area_1.state == "disarmed"
    assert area_2.state == "armed_away"

    area_1.coordinator.async_set_updated_data(
        _snapshot(
            areas={1: AreaState(area_id=1, name="Area 1", arm_mode=ArmMode.ARMED_STAY)}
        )
    )
    await hass.async_block_till_done()

    assert area_1.state == "armed_home"
    assert area_1.area == AreaState(
        area_id=1, name="Area 1", arm_mode=ArmMode.ARMED_STAY
    )


async def test_area_actions_and_pin_required(hass: HomeAssistant) -> None:
    """Test area action methods and PIN-required handling."""
    hub, entities = _setup_area_entities(
        hass,
        _snapshot(
            areas={1: AreaState(area_id=1, name="Area 1")},
            zones={
                1: ZoneState(
                    zone_id=1,
                    name="Front Door",
                    area_id=1,
                    open=True,
                    bypassed=False,
                ),
                2: ZoneState(zone_id=2, name="Window", open=False, bypassed=False),
                3: ZoneState(zone_id=3, name="Garage", open=True, bypassed=True),
            },
        ),
    )
    area_1 = entities[0]

    await area_1.async_alarm_arm_away(code="1234")
    hub.async_arm_area.assert_awaited_once_with(
        1, alarm_module.ArmMode.ARMED_AWAY, "1234"
    )

    hub.async_arm_area.reset_mock()
    await area_1.async_alarm_arm_home(code="1234")
    hub.async_arm_area.assert_awaited_once_with(
        1, alarm_module.ArmMode.ARMED_STAY, "1234"
    )

    hub.async_arm_area.reset_mock()
    await area_1.async_alarm_arm_night(code="1234")
    hub.async_arm_area.assert_awaited_once_with(
        1, alarm_module.ArmMode.ARMED_NIGHT, "1234"
    )

    hub.async_arm_area.reset_mock()
    hub.async_set_zone_bypass.reset_mock()
    await area_1.async_alarm_arm_custom_bypass(code="1234")
    hub.async_set_zone_bypass.assert_awaited_once_with(1, bypassed=True, pin="1234")
    hub.async_arm_area.assert_awaited_once_with(
        1,
        alarm_module._custom_bypass_mode(),
        "1234",
    )

    hub.async_disarm_area.side_effect = Elke27PinRequiredError
    with pytest.raises(
        HomeAssistantError, match="PIN required to perform this action."
    ):
        await area_1.async_alarm_disarm()

    hub.async_disarm_area.reset_mock()
    hub.async_disarm_area.side_effect = None
    hub.async_disarm_area.return_value = False
    with pytest.raises(
        HomeAssistantError, match="Area disarm command was not acknowledged."
    ):
        await area_1.async_alarm_disarm(code="1234")

    hub.async_set_zone_bypass.reset_mock()
    hub.async_arm_area.reset_mock()
    hub.async_set_zone_bypass.side_effect = None
    hub.async_set_zone_bypass.return_value = False
    with pytest.raises(HomeAssistantError, match="Zone 1 bypass was not acknowledged."):
        await area_1.async_alarm_arm_custom_bypass(code="1234")
    hub.async_arm_area.assert_not_awaited()

    hub.async_set_zone_bypass.reset_mock()
    hub.async_set_zone_bypass.return_value = True
    hub.async_set_zone_bypass.side_effect = Elke27PinRequiredError
    with pytest.raises(
        HomeAssistantError, match="PIN required to perform this action."
    ):
        await area_1.async_alarm_arm_custom_bypass(code="1234")

    hub.async_arm_area.reset_mock()
    hub.async_arm_area.side_effect = Elke27PinRequiredError
    with pytest.raises(
        HomeAssistantError, match="PIN required to perform this action."
    ):
        await area_1.async_alarm_arm_home(code="1234")

    hub.async_arm_area.reset_mock()
    hub.async_arm_area.side_effect = None
    hub.async_arm_area.return_value = False
    with pytest.raises(
        HomeAssistantError, match="Area arm command was not acknowledged."
    ):
        await area_1.async_alarm_arm_away(code="1234")


async def test_custom_bypass_handles_multiple_faulted_zones(
    hass: HomeAssistant,
) -> None:
    """Test custom bypass handles all faulted zones before arming."""
    hub, entities = _setup_area_entities(
        hass,
        _snapshot(
            areas={1: AreaState(area_id=1, name="Area 1")},
            zones={
                1: ZoneState(
                    zone_id=1,
                    name="Front Door",
                    area_id=1,
                    open=True,
                    bypassed=False,
                ),
                2: ZoneState(
                    zone_id=2,
                    name="Window",
                    area_id=1,
                    open=True,
                    bypassed=False,
                ),
            },
        ),
    )
    area_1 = entities[0]
    hub.async_set_zone_bypass.side_effect = [True, False]

    with pytest.raises(HomeAssistantError, match="Zone 2 bypass was not acknowledged."):
        await area_1.async_alarm_arm_custom_bypass(code="1234")

    assert hub.async_set_zone_bypass.await_count == 2
    hub.async_arm_area.assert_not_awaited()


async def test_custom_bypass_skips_other_area_faulted_zones(
    hass: HomeAssistant,
) -> None:
    """Test custom bypass only bypasses faulted zones assigned to the area."""
    hub, entities = _setup_area_entities(
        hass,
        _snapshot(
            areas={1: AreaState(area_id=1, name="Area 1")},
            zones={
                1: ZoneState(
                    zone_id=1,
                    name="Front Door",
                    area_id=1,
                    open=True,
                    bypassed=False,
                ),
                2: ZoneState(
                    zone_id=2,
                    name="Window",
                    area_id=2,
                    open=True,
                    bypassed=False,
                ),
            },
        ),
    )

    await entities[0].async_alarm_arm_custom_bypass(code="1234")

    hub.async_set_zone_bypass.assert_awaited_once_with(1, bypassed=True, pin="1234")
    hub.async_arm_area.assert_awaited_once()


def test_area_state_helpers() -> None:
    """Verify state mapping."""
    assert (
        alarm_module._area_state_to_ha(AreaState(area_id=1, alarm_active=True))
        == "triggered"
    )
    assert alarm_module._area_state_to_ha(AreaState(area_id=1)) == "disarmed"
    assert (
        alarm_module._area_state_to_ha(AreaState(area_id=1, arm_mode=ArmMode.DISARMED))
        == "disarmed"
    )
    assert (
        alarm_module._area_state_to_ha(
            AreaState(area_id=1, arm_mode=ArmMode.ARMED_STAY)
        )
        == "armed_home"
    )
    assert (
        alarm_module._area_state_to_ha(
            AreaState(area_id=1, arm_mode=ArmMode.ARMED_NIGHT)
        )
        == "armed_night"
    )
    assert (
        alarm_module._area_state_to_ha(
            AreaState(area_id=1, arm_mode=ArmMode.ARMED_AWAY)
        )
        == "armed_away"
    )


async def test_area_properties_when_missing(hass: HomeAssistant) -> None:
    """Verify properties handle missing area data."""
    hub, entities = _setup_area_entities(
        hass,
        _snapshot(areas={1: AreaState(area_id=1, name="Area 1")}),
    )
    area = entities[0]
    area.coordinator.async_set_updated_data(_snapshot())

    assert area.state is None
    hub.is_ready = False
    assert area.available is False


def test_normalize_code() -> None:
    """Verify code normalization."""
    assert alarm_module._normalize_code(None) is None
    assert alarm_module._normalize_code(" 1234 ") == "1234"
    with pytest.raises(HomeAssistantError):
        alarm_module._normalize_code("12ab")

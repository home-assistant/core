"""Tests for Ecovacs select entities."""

from dataclasses import dataclass

from deebot_client.command import Command
from deebot_client.commands.json import (
    SetAdvancedMode,
    SetBorderSpin,
    SetBorderSwitch,
    SetCarpetAutoFanBoost,
    SetChildLock,
    SetContinuousCleaning,
    SetCrossMapBorderWarning,
    SetMoveUpWarning,
    SetSafeProtect,
    SetTrueDetect,
)
from deebot_client.events import (
    AdvancedModeEvent,
    BorderSpinEvent,
    BorderSwitchEvent,
    CarpetAutoFanBoostEvent,
    ChildLockEvent,
    ContinuousCleaningEvent,
    CrossMapBorderWarningEvent,
    Event,
    MoveUpWarningEvent,
    SafeProtectEvent,
    TrueDetectEvent,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import block_till_done

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.SWITCH


@dataclass(frozen=True)
class SwitchTestCase:
    """Switch test."""

    entity_id: str
    event: Event
    command: type[Command]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_fixture", "tests"),
    [
        (
            "yna5x1",
            [
                SwitchTestCase(
                    "switch.ozmo_950_advanced_mode",
                    AdvancedModeEvent(True),
                    SetAdvancedMode,
                ),
                SwitchTestCase(
                    "switch.ozmo_950_continuous_cleaning",
                    ContinuousCleaningEvent(True),
                    SetContinuousCleaning,
                ),
                SwitchTestCase(
                    "switch.ozmo_950_carpet_auto_boost_suction",
                    CarpetAutoFanBoostEvent(True),
                    SetCarpetAutoFanBoost,
                ),
            ],
        ),
        (
            "5xu9h3",
            [
                SwitchTestCase(
                    "switch.goat_g1_advanced_mode",
                    AdvancedModeEvent(True),
                    SetAdvancedMode,
                ),
                SwitchTestCase(
                    "switch.goat_g1_true_detect",
                    TrueDetectEvent(True),
                    SetTrueDetect,
                ),
                SwitchTestCase(
                    "switch.goat_g1_border_switch",
                    BorderSwitchEvent(True),
                    SetBorderSwitch,
                ),
                SwitchTestCase(
                    "switch.goat_g1_child_lock",
                    ChildLockEvent(True),
                    SetChildLock,
                ),
                SwitchTestCase(
                    "switch.goat_g1_move_up_warning",
                    MoveUpWarningEvent(True),
                    SetMoveUpWarning,
                ),
                SwitchTestCase(
                    "switch.goat_g1_cross_map_border_warning",
                    CrossMapBorderWarningEvent(True),
                    SetCrossMapBorderWarning,
                ),
                SwitchTestCase(
                    "switch.goat_g1_safe_protect",
                    SafeProtectEvent(True),
                    SetSafeProtect,
                ),
            ],
        ),
        (
            "55uoqe",
            [
                SwitchTestCase(
                    "switch.dbmini_continuous_cleaning",
                    ContinuousCleaningEvent(True),
                    SetContinuousCleaning,
                ),
                SwitchTestCase(
                    "switch.dbmini_carpet_auto_boost_suction",
                    CarpetAutoFanBoostEvent(True),
                    SetCarpetAutoFanBoost,
                ),
                SwitchTestCase(
                    "switch.dbmini_true_detect",
                    TrueDetectEvent(True),
                    SetTrueDetect,
                ),
                SwitchTestCase(
                    "switch.dbmini_child_lock",
                    ChildLockEvent(True),
                    SetChildLock,
                ),
                SwitchTestCase(
                    "switch.dbmini_border_spin",
                    BorderSpinEvent(True),
                    SetBorderSpin,
                ),
            ],
        ),
    ],
    ids=["yna5x1", "5xu9h3", "55uoqe"],
)
async def test_switch_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
    tests: list[SwitchTestCase],
) -> None:
    """Test switch entities."""
    device = controller.devices[0]
    event_bus = device.events

    # Camera stream switches are also enabled by entity_registry_enabled_by_default but
    # are not capability-based; exclude them from the capability-switch assertion.
    capability_entity_ids = [
        e for e in hass.states.async_entity_ids() if "camera_stream" not in e
    ]
    assert capability_entity_ids == [test.entity_id for test in tests]
    for test_case in tests:
        entity_id = test_case.entity_id
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert state.state == STATE_OFF

        event_bus.notify(test_case.event)
        await block_till_done(hass, event_bus)

        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert snapshot(name=f"{entity_id}:state") == state
        assert state.state == STATE_ON

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}

        device._execute_command.reset_mock()
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        device._execute_command.assert_called_with(test_case.command(False))

        device._execute_command.reset_mock()
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        device._execute_command.assert_called_with(test_case.command(True))


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "yna5x1",
            [
                "switch.ozmo_950_advanced_mode",
                "switch.ozmo_950_continuous_cleaning",
                "switch.ozmo_950_carpet_auto_boost_suction",
                "switch.ozmo_950_camera_stream",
            ],
        ),
        (
            "5xu9h3",
            [
                "switch.goat_g1_advanced_mode",
                "switch.goat_g1_true_detect",
                "switch.goat_g1_border_switch",
                "switch.goat_g1_child_lock",
                "switch.goat_g1_move_up_warning",
                "switch.goat_g1_cross_map_border_warning",
                "switch.goat_g1_safe_protect",
                "switch.goat_g1_camera_stream",
            ],
        ),
        (
            "55uoqe",
            [
                "switch.dbmini_border_spin",
                "switch.dbmini_camera_stream",
            ],
        ),
    ],
    ids=["yna5x1", "5xu9h3", "55uoqe"],
)
async def test_disabled_by_default_switch_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_ids: list[str]
) -> None:
    """Test the disabled by default switch entities."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)

        assert (entry := entity_registry.async_get(entity_id)), (
            f"Entity registry entry for {entity_id} is missing"
        )
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


# ── CameraStreamSwitch functional tests ──────────────────────────────────────


class TestCameraStreamSwitch:
    """Functional tests for CameraStreamSwitch — requires both SWITCH and CAMERA platforms."""

    @pytest.fixture
    def platforms(self) -> list[Platform]:
        """Override platforms to load both switch and camera."""
        return [Platform.SWITCH, Platform.CAMERA]

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_turn_on_starts_stream(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
        mock_kvs_api,
    ) -> None:
        """Turning the switch ON delegates to camera entity and starts the stream."""
        _, session_instance = mock_kvs_stream_session

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.ozmo_950_camera_stream"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.ozmo_950_camera_stream")
        assert state is not None
        assert state.state == STATE_ON
        session_instance.start.assert_called_once()

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_turn_off_stops_stream(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
        mock_kvs_api,
    ) -> None:
        """Turning the switch OFF stops the stream."""
        _, session_instance = mock_kvs_stream_session

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.ozmo_950_camera_stream"},
            blocking=True,
        )
        await hass.async_block_till_done()

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.ozmo_950_camera_stream"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.ozmo_950_camera_stream")
        assert state is not None
        assert state.state == STATE_OFF
        session_instance.stop.assert_called_once()

    @pytest.mark.usefixtures("entity_registry_enabled_by_default")
    @pytest.mark.parametrize("device_fixture", ["yna5x1"])
    async def test_syncs_with_camera_service(
        self,
        hass: HomeAssistant,
        mock_kvs_stream_session,
        mock_kvs_api,
    ) -> None:
        """Switch state mirrors camera state when stream started via camera service."""
        await hass.services.async_call(
            "camera",
            "turn_on",
            {ATTR_ENTITY_ID: "camera.ozmo_950_camera"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.ozmo_950_camera_stream")
        assert state is not None
        assert state.state == STATE_ON

        await hass.services.async_call(
            "camera",
            "turn_off",
            {ATTR_ENTITY_ID: "camera.ozmo_950_camera"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.ozmo_950_camera_stream")
        assert state is not None
        assert state.state == STATE_OFF

"""Tests for the Bosch SHC button platform."""

from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

from boschshcpy import SHCSmokeDetector, SHCTwinguard
from boschshcpy.device import SHCDevice
from boschshcpy.models_impl import SHCMicromoduleRelay, SHCMotionDetector2
from boschshcpy.scenario import SHCScenario
from boschshcpy.services_impl import DetectionTestService, WalkTestService
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Load only the button platform."""
    return [Platform.BUTTON]


def _make_device(spec: type[SHCDevice], serial: str, device_id: str) -> MagicMock:
    """Build an autospecced SHC device with the base attributes SHCEntity needs."""
    device = create_autospec(spec, instance=True)
    device.serial = serial
    device.id = device_id
    device.root_device_id = "shc-test-uid"  # matches mock_session's hub unique_id
    device.name = "Test Device"
    device.manufacturer = "Bosch"
    device.device_model = "TEST_MODEL"
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    return device


def _make_scenario(scenario_id: str, name: str) -> MagicMock:
    """Build an autospecced SHCScenario."""
    scenario = create_autospec(SHCScenario, instance=True)
    scenario.id = scenario_id
    scenario.name = name
    return scenario


@pytest.fixture
def mock_motion_detector2() -> MagicMock:
    """Return a Motion Detector II with walk-test and detection-test both available."""
    device = _make_device(SHCMotionDetector2, "md2-serial", "md2-id")
    device.supports_walk_test = True
    device.walk_state = MagicMock()  # anything but None → walk-test buttons created
    device.supports_detection_test = True
    return device


async def _setup_button_platform(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Set up the bosch_shc config entry with only the button platform loaded."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.async_get_instance"),
        patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.BUTTON]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    mock_motion_detector2: MagicMock,
) -> None:
    """Every button entity is created for a fully-featured SHC installation."""
    mock_session.scenarios = [_make_scenario("sc-1", "Good Night")]
    mock_session.device_helper.micromodule_impulse_relays = [
        _make_device(SHCMicromoduleRelay, "ir-serial", "ir-id")
    ]
    mock_session.device_helper.smoke_detectors = [
        _make_device(SHCSmokeDetector, "sd-serial", "sd-id")
    ]
    mock_session.device_helper.twinguards = [
        _make_device(SHCTwinguard, "tg-serial", "tg-id")
    ]
    mock_session.device_helper.motion_detectors2 = [mock_motion_detector2]

    await _setup_button_platform(hass, mock_config_entry, mock_session)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_buttons_when_no_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """No button entities are created when all device lists are empty."""
    assert not er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )


@pytest.mark.parametrize(
    ("entity_id", "device_key", "mock_attr", "call_args"),
    [
        pytest.param(
            "button.test_shc_good_night", "scenario", "trigger", (), id="scenario"
        ),
        pytest.param(
            "button.test_device_trigger",
            "impulse_relay",
            "trigger_impulse_state",
            (),
            id="impulse_relay",
        ),
        pytest.param(
            "button.test_device_smoke_test",
            "smoke_detector",
            "smoketest_requested",
            (),
            id="smoke_test",
        ),
        pytest.param(
            "button.test_device_walk_test",
            "motion_detector2",
            "set_walk_state_request",
            (WalkTestService.WalkStateRequest.WALK_STATE_START,),
            id="walk_test_start",
        ),
        pytest.param(
            "button.test_device_stop_walk_test",
            "motion_detector2",
            "set_walk_state_request",
            (WalkTestService.WalkStateRequest.WALK_STATE_STOP,),
            id="walk_test_stop",
        ),
        pytest.param(
            "button.test_device_detection_test",
            "motion_detector2",
            "set_detection_state_request",
            (DetectionTestService.DetectionStateRequest.DETECTION_STATE_START,),
            id="detection_test_start",
        ),
        pytest.param(
            "button.test_device_stop_detection_test",
            "motion_detector2",
            "set_detection_state_request",
            (DetectionTestService.DetectionStateRequest.DETECTION_STATE_STOP,),
            id="detection_test_stop",
        ),
        pytest.param(
            "button.test_device_reset_tamper",
            "motion_detector2",
            "reset_tampered_state",
            (),
            id="reset_tamper",
        ),
    ],
)
async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    mock_motion_detector2: MagicMock,
    entity_id: str,
    device_key: str,
    mock_attr: str,
    call_args: tuple[Any, ...],
) -> None:
    """Pressing a button calls the matching boschshcpy method with the right args."""
    scenario = _make_scenario("sc-1", "Good Night")
    impulse_relay = _make_device(SHCMicromoduleRelay, "ir-serial", "ir-id")
    smoke_detector = _make_device(SHCSmokeDetector, "sd-serial", "sd-id")
    mock_session.scenarios = [scenario]
    mock_session.device_helper.micromodule_impulse_relays = [impulse_relay]
    mock_session.device_helper.smoke_detectors = [smoke_detector]
    mock_session.device_helper.motion_detectors2 = [mock_motion_detector2]

    await _setup_button_platform(hass, mock_config_entry, mock_session)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    device_by_key = {
        "scenario": scenario,
        "impulse_relay": impulse_relay,
        "smoke_detector": smoke_detector,
        "motion_detector2": mock_motion_detector2,
    }
    getattr(device_by_key[device_key], mock_attr).assert_called_once_with(*call_args)


@pytest.mark.parametrize(
    ("supports_walk_test", "walk_state_present", "supports_detection_test"),
    [
        pytest.param(False, False, False, id="neither_supported"),
        pytest.param(True, False, False, id="walk_test_service_absent"),
    ],
)
async def test_motion_detector2_optional_buttons_skipped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    supports_walk_test: bool,
    walk_state_present: bool,
    supports_detection_test: bool,
) -> None:
    """Walk-test and detection-test buttons are only created when supported."""
    device = _make_device(SHCMotionDetector2, "md2-serial", "md2-id")
    device.supports_walk_test = supports_walk_test
    device.walk_state = MagicMock() if walk_state_present else None
    device.supports_detection_test = supports_detection_test
    mock_session.device_helper.motion_detectors2 = [device]

    await _setup_button_platform(hass, mock_config_entry, mock_session)

    entity_ids = {
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    # The tamper-reset button is always created for a Motion Detector II.
    assert entity_ids == {"button.test_device_reset_tamper"}

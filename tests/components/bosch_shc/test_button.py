"""Tests for the Bosch SHC button platform."""

from unittest.mock import AsyncMock, MagicMock

from boschshcpy.services_impl import DetectionTestService, WalkTestService

from homeassistant.components.bosch_shc.button import SHCScenarioButton
from homeassistant.components.bosch_shc.const import DOMAIN, OPT_SCENARIOS_AS_BUTTONS
from homeassistant.core import HomeAssistant

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config_entry_with_options(options: dict) -> MockConfigEntry:
    """Return a config entry pre-loaded with the given options."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            "host": "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            "token": "abc:test-mac",
            "hostname": "test-mac",
        },
        options=options,
    )


# ---------------------------------------------------------------------------
# SHCRelayButton — micromodule_impulse_relays
# ---------------------------------------------------------------------------


async def test_relay_button_setup_and_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SHCRelayButton is created for each micromodule_impulse_relay and press triggers impulse."""
    device = make_device("relay-1", "Impulse Relay", status="AVAILABLE")
    device.trigger_impulse_state = MagicMock()

    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    await setup_integration(hass, mock_config_entry)

    # Primary entity: _attr_name=None → entity name == device name.
    state = hass.states.get("button.impulse_relay")
    assert state is not None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.impulse_relay"},
        blocking=True,
    )
    device.trigger_impulse_state.assert_called_once()


async def test_relay_button_excluded_device(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """An excluded device must not produce a button entity."""
    device = make_device("relay-excl", "Excluded Relay", status="AVAILABLE")
    device.trigger_impulse_state = MagicMock()

    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    entry = _make_config_entry_with_options({"excluded_devices": ["relay-excl"]})
    await setup_integration(hass, entry)

    assert hass.states.get("button.excluded_relay") is None


async def test_relay_button_excluded_by_room(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A relay device excluded by room_id must not produce a button entity."""
    device = make_device("relay-rm", "Room Relay", status="AVAILABLE", room_id="room-x")
    device.trigger_impulse_state = MagicMock()

    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    entry = _make_config_entry_with_options({"excluded_rooms": ["room-x"]})
    await setup_integration(hass, entry)

    assert hass.states.get("button.room_relay") is None


# ---------------------------------------------------------------------------
# SHCSmokeTestButton — smoke_detectors
# ---------------------------------------------------------------------------


async def test_smoke_test_button_excluded_device(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """An excluded smoke_detector must not produce a button entity."""
    device = make_device("sd-excl", "Excluded SD", status="AVAILABLE")
    device.smoketest_requested = MagicMock()

    mock_setup_dependencies.device_helper.smoke_detectors = [device]

    entry = _make_config_entry_with_options({"excluded_devices": ["sd-excl"]})
    await setup_integration(hass, entry)

    assert hass.states.get("button.excluded_sd_smoke_test") is None


async def test_smoke_test_button_setup_and_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SHCSmokeTestButton is created for smoke_detectors and press calls smoketest_requested."""
    device = make_device("sd-1", "Smoke Detector", status="AVAILABLE")
    device.smoketest_requested = MagicMock()

    mock_setup_dependencies.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    # _attr_name="Smoke Test" → entity id = "<device name> Smoke Test" slugified.
    state = hass.states.get("button.smoke_detector_smoke_test")
    assert state is not None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.smoke_detector_smoke_test"},
        blocking=True,
    )
    device.smoketest_requested.assert_called_once()


# ---------------------------------------------------------------------------
# SHCSmokeTestButton — twinguards
# ---------------------------------------------------------------------------


async def test_twinguard_smoke_test_button_setup_and_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SHCSmokeTestButton is also created for twinguards and calls smoketest_requested."""
    device = make_device("tg-1", "Twinguard", status="AVAILABLE")
    device.smoketest_requested = MagicMock()

    mock_setup_dependencies.device_helper.twinguards = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("button.twinguard_smoke_test")
    assert state is not None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.twinguard_smoke_test"},
        blocking=True,
    )
    device.smoketest_requested.assert_called_once()


async def test_twinguard_smoke_test_button_excluded_device(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """An excluded twinguard must not produce a button entity."""
    device = make_device("tg-excl", "Excluded TG", status="AVAILABLE")
    device.smoketest_requested = MagicMock()

    mock_setup_dependencies.device_helper.twinguards = [device]

    entry = _make_config_entry_with_options({"excluded_devices": ["tg-excl"]})
    await setup_integration(hass, entry)

    assert hass.states.get("button.excluded_tg_smoke_test") is None


# ---------------------------------------------------------------------------
# SHCWalkTestButton + SHCWalkTestStopButton
# ---------------------------------------------------------------------------


async def test_walk_test_buttons_setup_and_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Walk-test start and stop buttons are created for MD2 with WalkTest service."""
    device = make_device("md2-wt", "Motion Detector 2", status="AVAILABLE")
    device.supports_walk_test = True
    device.walk_state = "IDLE"  # not None → service is present
    device.async_set_walk_state_request = AsyncMock()
    device.supports_detection_test = False

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    start_state = hass.states.get("button.motion_detector_2_walk_test")
    stop_state = hass.states.get("button.motion_detector_2_walk_test_stop")
    assert start_state is not None
    assert stop_state is not None

    # Press start.
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.motion_detector_2_walk_test"},
        blocking=True,
    )
    device.async_set_walk_state_request.assert_awaited_once_with(
        WalkTestService.WalkStateRequest.WALK_STATE_START
    )

    device.async_set_walk_state_request.reset_mock()

    # Press stop.
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.motion_detector_2_walk_test_stop"},
        blocking=True,
    )
    device.async_set_walk_state_request.assert_awaited_once_with(
        WalkTestService.WalkStateRequest.WALK_STATE_STOP
    )


async def test_walk_test_skipped_when_service_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Walk-test buttons are NOT created when walk_state is None (service absent)."""
    device = make_device("md2-nowt", "Motion Detector 2 No WT", status="AVAILABLE")
    device.supports_walk_test = True
    device.walk_state = None  # service absent → skip
    device.supports_detection_test = False

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("button.motion_detector_2_no_wt_walk_test") is None
    assert hass.states.get("button.motion_detector_2_no_wt_walk_test_stop") is None


async def test_walk_test_skipped_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Walk-test buttons are NOT created when supports_walk_test is False."""
    device = make_device("md2-nosupp", "Motion Detector 2 NS", status="AVAILABLE")
    device.supports_walk_test = False
    device.walk_state = "IDLE"
    device.supports_detection_test = False

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("button.motion_detector_2_ns_walk_test") is None


async def test_md2_excluded_device_skips_all_buttons(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """An excluded MD2 device must not produce any walk-test or detection-test buttons."""
    device = make_device("md2-excl", "MD2 Excluded", status="AVAILABLE")
    device.supports_walk_test = True
    device.walk_state = "IDLE"
    device.supports_detection_test = True
    device.reset_tampered_state = MagicMock()

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    entry = _make_config_entry_with_options({"excluded_devices": ["md2-excl"]})
    await setup_integration(hass, entry)

    assert hass.states.get("button.md2_excluded_walk_test") is None
    assert hass.states.get("button.md2_excluded_detection_test") is None
    assert hass.states.get("button.md2_excluded_reset_tamper") is None


# ---------------------------------------------------------------------------
# SHCDetectionTestButton + SHCDetectionTestStopButton
# ---------------------------------------------------------------------------


async def test_detection_test_buttons_setup_and_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Detection-test start and stop buttons are created when supports_detection_test."""
    device = make_device("md2-dt", "Motion Detector 2 DT", status="AVAILABLE")
    device.supports_walk_test = False
    device.supports_detection_test = True
    device.async_set_detection_state_request = AsyncMock()
    # No tamper-reset on this device.
    del device.reset_tampered_state

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    start_state = hass.states.get("button.motion_detector_2_dt_detection_test")
    stop_state = hass.states.get("button.motion_detector_2_dt_detection_test_stop")
    assert start_state is not None
    assert stop_state is not None

    # Press start.
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.motion_detector_2_dt_detection_test"},
        blocking=True,
    )
    device.async_set_detection_state_request.assert_awaited_once_with(
        DetectionTestService.DetectionStateRequest.DETECTION_STATE_START
    )

    device.async_set_detection_state_request.reset_mock()

    # Press stop.
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.motion_detector_2_dt_detection_test_stop"},
        blocking=True,
    )
    device.async_set_detection_state_request.assert_awaited_once_with(
        DetectionTestService.DetectionStateRequest.DETECTION_STATE_STOP
    )


async def test_detection_test_skipped_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Detection-test buttons are NOT created when supports_detection_test is False."""
    device = make_device("md2-nodt", "Motion Detector 2 NDT", status="AVAILABLE")
    device.supports_walk_test = False
    device.supports_detection_test = False

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("button.motion_detector_2_ndt_detection_test") is None
    assert hass.states.get("button.motion_detector_2_ndt_detection_test_stop") is None


# ---------------------------------------------------------------------------
# SHCTamperResetButton
# ---------------------------------------------------------------------------


async def test_tamper_reset_button_setup_and_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Tamper-reset button is created when device has reset_tampered_state attr."""
    device = make_device("md2-tr", "Motion Detector 2 TR", status="AVAILABLE")
    device.supports_walk_test = False
    device.supports_detection_test = False
    # Having the attribute triggers entity creation.
    device.reset_tampered_state = MagicMock()
    device.async_reset_tampered_state = AsyncMock()

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("button.motion_detector_2_tr_reset_tamper")
    assert state is not None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.motion_detector_2_tr_reset_tamper"},
        blocking=True,
    )
    device.async_reset_tampered_state.assert_awaited_once()


# ---------------------------------------------------------------------------
# SHCScenarioButton
# ---------------------------------------------------------------------------


async def test_scenario_button_not_created_without_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Scenario buttons are NOT created when OPT_SCENARIOS_AS_BUTTONS is False/absent."""
    scenario = MagicMock()
    scenario.id = "scen-1"
    scenario.name = "Good Morning"
    scenario.trigger = MagicMock()

    mock_setup_dependencies.scenarios = [scenario]

    await setup_integration(hass, mock_config_entry)

    # The option is off by default; no scenario button should appear.
    assert hass.states.get("button.shc012345_good_morning") is None


async def test_scenario_button_created_with_option(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Scenario buttons ARE created when OPT_SCENARIOS_AS_BUTTONS option is True."""
    scenario = MagicMock()
    scenario.id = "scen-1"
    scenario.name = "Good Morning"
    scenario.trigger = MagicMock()

    mock_setup_dependencies.scenarios = [scenario]

    entry = _make_config_entry_with_options({OPT_SCENARIOS_AS_BUTTONS: True})
    await setup_integration(hass, entry)

    # Scenario button entity id = <entry_title>_<scenario_name> slugified.
    state = hass.states.get("button.shc012345_good_morning")
    assert state is not None


async def test_scenario_button_press_calls_trigger(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Pressing a scenario button calls scenario.trigger()."""
    scenario = MagicMock()
    scenario.id = "scen-42"
    scenario.name = "Lights Out"
    scenario.trigger = MagicMock()

    mock_setup_dependencies.scenarios = [scenario]

    entry = _make_config_entry_with_options({OPT_SCENARIOS_AS_BUTTONS: True})
    await setup_integration(hass, entry)

    state = hass.states.get("button.shc012345_lights_out")
    assert state is not None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.shc012345_lights_out"},
        blocking=True,
    )
    scenario.trigger.assert_called_once()


async def test_scenario_button_bad_payload_skipped(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A scenario raising AttributeError during setup is skipped gracefully."""

    class BadScenario:
        """Scenario whose .name property always raises AttributeError."""

        id = "bad-scen"

        @property
        def name(self):
            raise AttributeError("bad payload")

    good_scenario = MagicMock()
    good_scenario.id = "good-scen"
    good_scenario.name = "Good Evening"
    good_scenario.trigger = MagicMock()

    mock_setup_dependencies.scenarios = [BadScenario(), good_scenario]

    entry = _make_config_entry_with_options({OPT_SCENARIOS_AS_BUTTONS: True})
    await setup_integration(hass, entry)

    # The good scenario is still registered; the bad one was skipped with a warning.
    assert hass.states.get("button.shc012345_good_evening") is not None


def test_scenario_button_device_info_none_when_no_shc_device() -> None:
    """SHCScenarioButton.device_info returns None when shc_device is None."""
    scenario = MagicMock()
    scenario.id = "scen-x"
    scenario.name = "Noop"

    button = SHCScenarioButton(
        scenario=scenario,
        entry_unique_id="uid",
        entry_id="eid",
        shc_device=None,
    )
    assert button.device_info is None


# ---------------------------------------------------------------------------
# Multiple entities on a single MD2 device
# ---------------------------------------------------------------------------


async def test_md2_all_services_creates_all_buttons(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """An MD2 with walk-test + detection-test + tamper-reset produces 5 buttons."""
    device = make_device("md2-full", "MD2 Full", status="AVAILABLE")
    device.supports_walk_test = True
    device.walk_state = "IDLE"
    device.async_set_walk_state_request = AsyncMock()
    device.supports_detection_test = True
    device.async_set_detection_state_request = AsyncMock()
    device.reset_tampered_state = MagicMock()
    device.async_reset_tampered_state = AsyncMock()

    mock_setup_dependencies.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("button.md2_full_walk_test") is not None
    assert hass.states.get("button.md2_full_walk_test_stop") is not None
    assert hass.states.get("button.md2_full_detection_test") is not None
    assert hass.states.get("button.md2_full_detection_test_stop") is not None
    assert hass.states.get("button.md2_full_reset_tamper") is not None

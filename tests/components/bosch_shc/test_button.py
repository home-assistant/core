"""Tests for the Bosch SHC button platform."""

from unittest.mock import MagicMock, patch

from boschshcpy.services_impl import DetectionTestService, WalkTestService

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "bosch_shc"

MOCK_ENTRY_DATA = {
    "host": "1.2.3.4",
    "ssl_certificate": "/fake/cert.pem",
    "ssl_key": "/fake/key.pem",
    "hostname": "shc012345",
    "token": "token:shc012345",
}


def _make_mock_session(
    scenarios=None,
    impulse_relays=None,
    smoke_detectors=None,
    twinguards=None,
    motion_detectors2=None,
):
    """Build a minimal mock SHCSession."""
    session = MagicMock()
    session.information.unique_id = "shc-test-uid"
    session.information.version = "9.99"
    session.information.updateState.name = "UP_TO_DATE"
    session.scenarios = scenarios or []
    session.device_helper.micromodule_impulse_relays = impulse_relays or []
    session.device_helper.smoke_detectors = smoke_detectors or []
    session.device_helper.twinguards = twinguards or []
    session.device_helper.motion_detectors2 = motion_detectors2 or []
    # Other device_helper properties used by other platforms
    session.device_helper.shutter_contacts = []
    session.device_helper.shutter_contacts2 = []
    session.device_helper.shutter_controls = []
    session.device_helper.micromodule_shutter_controls = []
    session.device_helper.micromodule_blinds = []
    session.device_helper.micromodule_relays = []
    session.device_helper.light_switches_bsm = []
    session.device_helper.micromodule_light_attached = []
    session.device_helper.micromodule_light_controls = []
    session.device_helper.smart_plugs = []
    session.device_helper.smart_plugs_compact = []
    session.device_helper.climate_controls = []
    session.device_helper.thermostats = []
    session.device_helper.wallthermostats = []
    session.device_helper.roomthermostats = []
    session.device_helper.motion_detectors = []
    session.device_helper.universal_switches = []
    session.device_helper.camera_eyes = []
    session.device_helper.camera_360 = []
    session.device_helper.camera_outdoor_gen2 = []
    session.device_helper.heating_circuits = []
    return session


def _make_mock_device(serial="device-serial-1", device_id="device-id-1"):
    """Build a minimal mock SHCDevice."""
    device = MagicMock()
    device.serial = serial
    device.id = device_id
    device.root_device_id = device_id
    device.name = "Test Device"
    device.manufacturer = "Bosch"
    device.device_model = "TEST_MODEL"
    device.status = "AVAILABLE"
    device.deleted = False
    device.device_services = []
    return device


async def _setup_entry(hass: HomeAssistant, session: MagicMock) -> MockConfigEntry:
    """Create and set up a mock config entry with the given session."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_ENTRY_DATA,
        unique_id="shc012345",
        title="Test SHC",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_scenario_button_created(hass: HomeAssistant) -> None:
    """Scenario buttons are created for each SHC scenario."""
    scenario = MagicMock()
    scenario.id = "sc-1"
    scenario.name = "Good Night"
    session = _make_mock_session(scenarios=[scenario])

    await _setup_entry(hass, session)

    state = hass.states.get("button.test_shc_good_night")
    assert state is not None


async def test_scenario_button_press(hass: HomeAssistant) -> None:
    """Pressing a scenario button calls scenario.trigger via executor."""
    scenario = MagicMock()
    scenario.id = "sc-2"
    scenario.name = "Away Mode"
    session = _make_mock_session(scenarios=[scenario])

    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_shc_away_mode"},
        blocking=True,
    )

    scenario.trigger.assert_called_once()


async def test_impulse_relay_button(hass: HomeAssistant) -> None:
    """Impulse relay button calls trigger_impulse_state via executor."""
    device = _make_mock_device(serial="ir-serial", device_id="ir-id")
    session = _make_mock_session(impulse_relays=[device])

    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("button.test_device_trigger")
    assert state is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device_trigger"},
        blocking=True,
    )

    device.trigger_impulse_state.assert_called_once()


async def test_smoke_test_button_smoke_detector(hass: HomeAssistant) -> None:
    """Smoke test button for smoke detector calls smoketest_requested."""
    device = _make_mock_device(serial="sd-serial", device_id="sd-id")
    session = _make_mock_session(smoke_detectors=[device])

    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("button.test_device_smoke_test")
    assert state is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device_smoke_test"},
        blocking=True,
    )

    device.smoketest_requested.assert_called_once()


async def test_smoke_test_button_twinguard(hass: HomeAssistant) -> None:
    """Smoke test button for twinguard calls smoketest_requested."""
    device = _make_mock_device(serial="tg-serial", device_id="tg-id")
    session = _make_mock_session(twinguards=[device])

    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("button.test_device_smoke_test")
    assert state is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device_smoke_test"},
        blocking=True,
    )

    device.smoketest_requested.assert_called_once()


async def test_walk_test_buttons(hass: HomeAssistant) -> None:
    """WalkTest start/stop buttons created and each calls correct method."""
    device = _make_mock_device(serial="md2-serial", device_id="md2-id")
    device.supports_walk_test = True
    device.walk_state = MagicMock()  # not None → gate passes
    device.supports_detection_test = False

    session = _make_mock_session(motion_detectors2=[device])

    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    start_state = hass.states.get("button.test_device_walk_test")
    stop_state = hass.states.get("button.test_device_stop_walk_test")
    assert start_state is not None
    assert stop_state is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device_walk_test"},
        blocking=True,
    )
    device.set_walk_state_request.assert_called_once_with(
        WalkTestService.WalkStateRequest.WALK_STATE_START
    )
    device.set_walk_state_request.reset_mock()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device_stop_walk_test"},
        blocking=True,
    )
    device.set_walk_state_request.assert_called_once_with(
        WalkTestService.WalkStateRequest.WALK_STATE_STOP
    )


async def test_walk_test_skipped_when_service_absent(hass: HomeAssistant) -> None:
    """WalkTest buttons are not created when walk_state is None."""
    device = _make_mock_device(serial="md2-serial", device_id="md2-id")
    device.supports_walk_test = True
    device.walk_state = None  # gate fails
    device.supports_detection_test = False

    session = _make_mock_session(motion_detectors2=[device])

    await _setup_entry(hass, session)

    assert hass.states.get("button.test_device_walk_test") is None
    assert hass.states.get("button.test_device_stop_walk_test") is None


async def test_detection_test_buttons(hass: HomeAssistant) -> None:
    """DetectionTest start/stop buttons created and call correct methods."""
    device = _make_mock_device(serial="md2-serial", device_id="md2-id")
    device.supports_walk_test = False
    device.walk_state = None
    device.supports_detection_test = True

    session = _make_mock_session(motion_detectors2=[device])

    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    start_state = hass.states.get("button.test_device_detection_test")
    stop_state = hass.states.get("button.test_device_stop_detection_test")
    assert start_state is not None
    assert stop_state is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device_detection_test"},
        blocking=True,
    )
    device.set_detection_state_request.assert_called_once_with(
        DetectionTestService.DetectionStateRequest.DETECTION_STATE_START
    )
    device.set_detection_state_request.reset_mock()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device_stop_detection_test"},
        blocking=True,
    )
    device.set_detection_state_request.assert_called_once_with(
        DetectionTestService.DetectionStateRequest.DETECTION_STATE_STOP
    )


async def test_tamper_reset_button(hass: HomeAssistant) -> None:
    """Tamper reset button is always created for MD2 and calls reset_tampered_state."""
    device = _make_mock_device(serial="md2-serial", device_id="md2-id")
    device.supports_walk_test = False
    device.walk_state = None
    device.supports_detection_test = False

    session = _make_mock_session(motion_detectors2=[device])

    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("button.test_device_reset_tamper")
    assert state is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_device_reset_tamper"},
        blocking=True,
    )

    device.reset_tampered_state.assert_called_once()


async def test_no_buttons_when_no_devices(hass: HomeAssistant) -> None:
    """No button entities are created when all device lists are empty."""
    session = _make_mock_session()
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    button_states = [
        s for eid, s in hass.states.async_all() if eid.startswith("button.")
    ]
    assert len(button_states) == 0

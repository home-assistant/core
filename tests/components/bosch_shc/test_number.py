"""Tests for the Bosch SHC number platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
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
    thermostats=None,
    roomthermostats=None,
    micromodule_impulse_relays=None,
):
    """Build a minimal mock SHCSession."""
    session = MagicMock()
    session.information.unique_id = "shc-test-uid"
    session.information.version = "9.99"
    session.information.updateState.name = "UP_TO_DATE"
    session.scenarios = []
    session.device_helper.thermostats = thermostats or []
    session.device_helper.roomthermostats = roomthermostats or []
    session.device_helper.micromodule_impulse_relays = micromodule_impulse_relays or []
    # Other device_helper properties used by other platforms
    session.device_helper.shutter_contacts = []
    session.device_helper.shutter_contacts2 = []
    session.device_helper.shutter_controls = []
    session.device_helper.micromodule_shutter_controls = []
    session.device_helper.micromodule_blinds = []
    session.device_helper.micromodule_relays = []
    session.device_helper.micromodule_light_controls = []
    session.device_helper.micromodule_light_attached = []
    session.device_helper.light_switches_bsm = []
    session.device_helper.climate_controls = []
    session.device_helper.wallthermostats = []
    session.device_helper.motion_detectors = []
    session.device_helper.motion_detectors2 = []
    session.device_helper.smart_plugs = []
    session.device_helper.smart_plugs_compact = []
    session.device_helper.smoke_detectors = []
    session.device_helper.twinguards = []
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


async def _set_value(hass: HomeAssistant, entity_id: str, value: float) -> None:
    """Call the set_value service for the given number entity."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )


# ---------------------------------------------------------------------------
# Thermostat temperature offset
# ---------------------------------------------------------------------------


async def test_thermostat_offset_created(hass: HomeAssistant) -> None:
    """Thermostat offset number created for every thermostat."""
    device = _make_mock_device(serial="trv-1", device_id="trv-id-1")
    device.offset = 0.5
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = False

    session = _make_mock_session(thermostats=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("number.test_device_temperature_offset")
    assert state is not None
    assert float(state.state) == 0.5


async def test_thermostat_offset_set_value(hass: HomeAssistant) -> None:
    """Setting offset calls setattr on the device."""
    device = _make_mock_device(serial="trv-1", device_id="trv-id-1")
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = False

    session = _make_mock_session(thermostats=[device])
    await _setup_entry(hass, session)

    await _set_value(hass, "number.test_device_temperature_offset", 1.5)

    assert device.offset == 1.5


async def test_thermostat_offset_for_roomthermostat(hass: HomeAssistant) -> None:
    """Thermostat offset number also created for roomthermostats."""
    device = _make_mock_device(serial="rt2-1", device_id="rt2-id-1")
    device.offset = -0.5
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = False

    session = _make_mock_session(roomthermostats=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("number.test_device_temperature_offset")
    assert state is not None
    assert float(state.state) == -0.5


# ---------------------------------------------------------------------------
# Impulse relay length
# ---------------------------------------------------------------------------


async def test_impulse_length_created(hass: HomeAssistant) -> None:
    """Impulse-length number created when impulse_length is not None."""
    device = _make_mock_device(serial="relay-1", device_id="relay-id-1")
    device.impulse_length = 20  # 20 tenths = 2.0 s

    session = _make_mock_session(micromodule_impulse_relays=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("number.test_device_impulse_length")
    assert state is not None
    assert float(state.state) == 2.0


async def test_impulse_length_set_value(hass: HomeAssistant) -> None:
    """Setting impulse length converts seconds to tenths of seconds."""
    device = _make_mock_device(serial="relay-1", device_id="relay-id-1")
    device.impulse_length = 20

    session = _make_mock_session(micromodule_impulse_relays=[device])
    await _setup_entry(hass, session)

    await _set_value(hass, "number.test_device_impulse_length", 3.5)

    assert device.impulse_length == 35


async def test_impulse_length_skipped_when_none(hass: HomeAssistant) -> None:
    """Impulse-length number not created when impulse_length is None."""
    device = _make_mock_device(serial="relay-2", device_id="relay-id-2")
    device.impulse_length = None

    session = _make_mock_session(micromodule_impulse_relays=[device])
    await _setup_entry(hass, session)

    assert hass.states.get("number.test_device_impulse_length") is None


# ---------------------------------------------------------------------------
# Display brightness
# ---------------------------------------------------------------------------


async def test_display_brightness_created(hass: HomeAssistant) -> None:
    """Display brightness number created when supported and not None."""
    device = _make_mock_device(serial="trv-gen2-1", device_id="trv-gen2-id-1")
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = True
    device.display_brightness = 50
    device.display_on_time = None
    svc = MagicMock()
    svc.display_brightness_min = 0
    svc.display_brightness_max = 100
    device._display_config_service = svc

    session = _make_mock_session(thermostats=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("number.test_device_display_brightness")
    assert state is not None
    assert float(state.state) == 50.0


async def test_display_brightness_set_value(hass: HomeAssistant) -> None:
    """Setting display brightness calls setattr on the device."""
    device = _make_mock_device(serial="trv-gen2-1", device_id="trv-gen2-id-1")
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = True
    device.display_brightness = 50
    device.display_on_time = None
    svc = MagicMock()
    svc.display_brightness_min = 0
    svc.display_brightness_max = 100
    device._display_config_service = svc

    session = _make_mock_session(thermostats=[device])
    await _setup_entry(hass, session)

    await _set_value(hass, "number.test_device_display_brightness", 75.0)

    assert device.display_brightness == 75


async def test_display_brightness_skipped_when_none(hass: HomeAssistant) -> None:
    """Display brightness number not created when display_brightness is None."""
    device = _make_mock_device(serial="trv-gen2-2", device_id="trv-gen2-id-2")
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = True
    device.display_brightness = None
    device.display_on_time = None

    session = _make_mock_session(thermostats=[device])
    await _setup_entry(hass, session)

    assert hass.states.get("number.test_device_display_brightness") is None


# ---------------------------------------------------------------------------
# Display on-time
# ---------------------------------------------------------------------------


async def test_display_on_time_created(hass: HomeAssistant) -> None:
    """Display on-time number created when supported and not None."""
    device = _make_mock_device(serial="trv-gen2-3", device_id="trv-gen2-id-3")
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = True
    device.display_brightness = None
    device.display_on_time = 30
    svc = MagicMock()
    svc.display_on_time_min = 0
    svc.display_on_time_max = 3600
    device._display_config_service = svc

    session = _make_mock_session(thermostats=[device])
    entry = await _setup_entry(hass, session)
    assert entry.state.value == "loaded"

    state = hass.states.get("number.test_device_display_on_time")
    assert state is not None
    assert float(state.state) == 30.0


async def test_display_on_time_set_value(hass: HomeAssistant) -> None:
    """Setting display on-time calls setattr on the device."""
    device = _make_mock_device(serial="trv-gen2-3", device_id="trv-gen2-id-3")
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = True
    device.display_brightness = None
    device.display_on_time = 30
    svc = MagicMock()
    svc.display_on_time_min = 0
    svc.display_on_time_max = 3600
    device._display_config_service = svc

    session = _make_mock_session(thermostats=[device])
    await _setup_entry(hass, session)

    await _set_value(hass, "number.test_device_display_on_time", 60.0)

    assert device.display_on_time == 60


async def test_display_on_time_skipped_when_none(hass: HomeAssistant) -> None:
    """Display on-time number not created when display_on_time is None."""
    device = _make_mock_device(serial="trv-gen2-4", device_id="trv-gen2-id-4")
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.supports_display_configuration = True
    device.display_brightness = None
    device.display_on_time = None

    session = _make_mock_session(thermostats=[device])
    await _setup_entry(hass, session)

    assert hass.states.get("number.test_device_display_on_time") is None

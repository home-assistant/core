"""bosch_shc session fixtures."""

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

from boschshcpy import (
    BatteryLevelService,
    BypassService,
    PowerSwitchService,
    RoutingService,
    SHCBatteryDevice,
    SHCLightSwitchBSM,
    SHCMicromoduleBlinds,
    SHCMicromoduleRelay,
    SHCMotionDetector,
    SHCMotionDetector2,
    SHCOutdoorSiren,
    SHCPresenceSimulationSystem,
    SHCShutterContact,
    SHCShutterContact2,
    SHCShutterContact2Plus,
    SHCShutterControl,
    SHCSmartPlug,
    SHCSmartPlugCompact,
    SHCSmokeDetector,
    SHCThermostat,
    SHCThermostatGen2,
    SHCTwinguard,
    ShutterContactService,
    ShutterControlService,
    SilentModeService,
    ThermostatService,
)
from boschshcpy.services_impl import (
    OutdoorSirenService,
    PresenceSimulationConfigurationService,
    ValveTappetService,
)
import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock bosch_shc config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )


# Keep in sync with binary_sensor.py's device_helper buckets — a bucket
# missing here breaks the mock_session fixture.
_EMPTY_DEVICE_BUCKETS: dict[str, Any] = {
    bucket: []
    for bucket in (
        "camera_360",
        "camera_eyes",
        "light_switches_bsm",
        "micromodule_blinds",
        "micromodule_dimmers",
        "micromodule_impulse_relays",
        "micromodule_light_attached",
        "micromodule_relays",
        "micromodule_shutter_controls",
        "motion_detectors",
        "motion_detectors2",
        "outdoor_sirens",
        "roomthermostats",
        "shutter_contacts",
        "shutter_contacts2",
        "shutter_controls",
        "smart_plugs",
        "smart_plugs_compact",
        "smoke_detectors",
        "thermostats",
        "twinguards",
        "universal_switches",
        "wallthermostats",
        "water_leakage_detectors",
    )
} | {
    # Not a list bucket — presence_simulation_system is a single optional
    # device on device_helper, not a device_helper.<x> list of devices.
    "presence_simulation_system": None,
}


@pytest.fixture
def device_buckets(request: pytest.FixtureRequest) -> dict[str, Any]:
    """device_helper buckets for the mock session.

    Empty by default; a test overrides specific buckets via
    ``@pytest.mark.parametrize("device_buckets", [{...}], indirect=True)``.
    """
    overrides: dict[str, Any] = getattr(request, "param", {})
    return {**_EMPTY_DEVICE_BUCKETS, **overrides}


@pytest.fixture
def mock_session(device_buckets: dict[str, Any]) -> Generator[MagicMock]:
    """Mock SHCSession, patched in for the duration of the test."""
    session = MagicMock()
    session.information.unique_id = "test-mac"
    session.information.updateState.name = "UP_TO_DATE"
    session.information.version = "2.0"
    session.device_helper = SimpleNamespace(**device_buckets)
    with patch("homeassistant.components.bosch_shc.SHCSession", return_value=session):
        yield session


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the bosch_shc integration for testing."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def battery_only_device(
    device_id: str = "hdm:HomeMaticIP:motion1",
    name: str = "Motion",
    device_services: list[Any] | None = None,
) -> SHCBatteryDevice:
    """Build a minimal device double for the motion_detectors bucket.

    motion_detectors only ever backs a single BatterySensor entity (unlike
    shutter_contacts, which backs both a ShutterContactSensor and a
    BatterySensor for the same device) — the single-entity shape keeps these
    entity.py tests free of a second entity's subscribe/unsubscribe calls.
    """
    device = create_autospec(SHCBatteryDevice, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.batterylevel = BatteryLevelService.State.OK
    device.device_services = device_services or []
    device.manufacturer = "Bosch"
    device.device_model = "MD"
    device.status = "AVAILABLE"
    device.deleted = False
    return device


def outdoor_siren_device(
    device_id: str = "hdm:ZigBee:outdoorsiren1",
    name: str = "Outdoor Siren",
    sound_level: OutdoorSirenService.SoundLevel = OutdoorSirenService.SoundLevel.MEDIUM,
) -> SHCOutdoorSiren:
    """Build a minimal device double for the outdoor_sirens bucket."""
    device = create_autospec(SHCOutdoorSiren, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "OUTDOOR_SIREN"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    siren_service = create_autospec(OutdoorSirenService, instance=True)
    siren_service.sound_level = sound_level
    device.siren = siren_service
    return device


def shutter_control_device(
    device_id: str = "hdm:ZigBee:shutter1",
    name: str = "Shutter",
    device_model: str = "BBL",
    level: float = 1.0,
    operation_state: ShutterControlService.State = ShutterControlService.State.STOPPED,
) -> SHCShutterControl:
    """Build a minimal device double for the shutter_controls/micromodule_shutter_controls buckets."""
    device = create_autospec(SHCShutterControl, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = device_model
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.level = level
    device.operation_state = operation_state
    return device


def micromodule_blinds_device(
    device_id: str = "hdm:ZigBee:blinds1",
    name: str = "Blinds",
    level: float = 1.0,
    current_angle: float = 0.0,
    operation_state: ShutterControlService.State = ShutterControlService.State.STOPPED,
) -> SHCMicromoduleBlinds:
    """Build a minimal device double for the micromodule_blinds bucket."""
    device = create_autospec(SHCMicromoduleBlinds, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "MICROMODULE_BLINDS"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.level = level
    device.current_angle = current_angle
    device.operation_state = operation_state
    return device


def smart_plug_device(
    device_id: str = "hdm:ZigBee:plug1",
    name: str = "Smart Plug",
    routing: RoutingService.State = RoutingService.State.DISABLED,
    supports_energy_saving_mode: bool = False,
    energy_saving_mode_enabled: bool = False,
) -> SHCSmartPlug:
    """Build a minimal device double for the smart_plugs bucket."""
    device = create_autospec(SHCSmartPlug, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "PSM"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.switchstate = PowerSwitchService.State.OFF
    device.routing = routing
    device.supports_energy_saving_mode = supports_energy_saving_mode
    device.energy_saving_mode_enabled = energy_saving_mode_enabled
    return device


def smart_plug_compact_device(
    device_id: str = "hdm:ZigBee:plugcompact1",
    name: str = "Smart Plug Compact",
    supports_energy_saving_mode: bool = False,
    energy_saving_mode_enabled: bool = False,
) -> SHCSmartPlugCompact:
    """Build a minimal device double for the smart_plugs_compact bucket."""
    device = create_autospec(SHCSmartPlugCompact, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "PLUG_COMPACT"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.switchstate = PowerSwitchService.State.OFF
    device.supports_energy_saving_mode = supports_energy_saving_mode
    device.energy_saving_mode_enabled = energy_saving_mode_enabled
    return device


def thermostat_device(
    device_id: str = "hdm:ZigBee:thermostat1",
    name: str = "Thermostat",
    child_lock: ThermostatService.State = ThermostatService.State.OFF,
    position: int = 50,
    valvestate: ValveTappetService.State = ValveTappetService.State.VALVE_ADAPTION_SUCCESSFUL,
    supports_silentmode: bool = False,
    silentmode: SilentModeService.State = SilentModeService.State.MODE_NORMAL,
) -> SHCThermostat:
    """Build a minimal device double for the thermostats/roomthermostats/wallthermostats buckets."""
    device = create_autospec(SHCThermostat, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "TRV"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.child_lock = child_lock
    device.position = position
    device.valvestate = valvestate
    device.supports_silentmode = supports_silentmode
    device.silentmode = silentmode
    return device


def thermostat_gen2_device(
    device_id: str = "hdm:ZigBee:thermostatgen2_1",
    name: str = "Thermostat Gen2",
    supports_display_configuration: bool = False,
    humidity_warning_enabled: bool = False,
) -> SHCThermostatGen2:
    """Build a minimal device double for the thermostats/roomthermostats buckets (Gen2)."""
    device = create_autospec(SHCThermostatGen2, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "TRV_GEN2"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.supports_display_configuration = supports_display_configuration
    device.humidity_warning_enabled = humidity_warning_enabled
    return device


def micromodule_relay_device(
    device_id: str = "hdm:ZigBee:relay1",
    name: str = "Relay",
    child_lock: bool = False,
    supports_switch_configuration: bool = False,
    swap_inputs: bool = False,
    swap_outputs: bool = False,
) -> SHCMicromoduleRelay:
    """Build a minimal device double for the micromodule_relays bucket."""
    device = create_autospec(SHCMicromoduleRelay, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "MICROMODULE_RELAY"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.child_lock = child_lock
    device.supports_switch_configuration = supports_switch_configuration
    device.swap_inputs = swap_inputs
    device.swap_outputs = swap_outputs
    return device


def light_switch_bsm_device(
    device_id: str = "hdm:ZigBee:lightswitch1",
    name: str = "Light switch",
    child_lock: bool = False,
) -> SHCLightSwitchBSM:
    """Build a minimal device double for the light_switches_bsm bucket.

    Backs both the primary "lightswitch" switch and the new child-lock
    switch, so a unique_id collision between the two would surface here.
    """
    device = create_autospec(SHCLightSwitchBSM, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "LIGHT_SWITCH_BSM"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.switchstate = PowerSwitchService.State.OFF
    device.child_lock = child_lock
    return device


def presence_simulation_system_device(
    device_id: str = "presenceSimulationService",
    name: str = "Presence Simulation",
    enabled: bool = False,
) -> SHCPresenceSimulationSystem:
    """Build a minimal device double for the presence_simulation_system slot."""
    device = create_autospec(SHCPresenceSimulationSystem, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "PRESENCE_SIMULATION_SERVICE"
    device.device_services = [
        create_autospec(
            PresenceSimulationConfigurationService, instance=True, spec_set=True
        )
    ]
    device.deleted = False
    device.status = "AVAILABLE"
    device.enabled = enabled
    return device


def shutter_contact_device(
    device_id: str = "hdm:ZigBee:shuttercontact1",
    name: str = "Shutter contact",
    device_class: str = "GENERIC",
    state: ShutterContactService.State = ShutterContactService.State.CLOSED,
) -> SHCShutterContact:
    """Build a minimal device double for the shutter_contacts bucket."""
    device = create_autospec(SHCShutterContact, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "SWD"
    device.device_class = device_class
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.state = state
    return device


def shutter_contact2_device(
    device_id: str = "hdm:ZigBee:shuttercontact1",
    name: str = "Shutter contact",
    bypass: BypassService.State = BypassService.State.BYPASS_INACTIVE,
    bypass_infinite: bool = False,
) -> SHCShutterContact2:
    """Build a minimal device double for the shutter_contacts2 bucket."""
    device = create_autospec(SHCShutterContact2, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "SWD2"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.bypass = bypass
    device.bypass_infinite = bypass_infinite
    return device


def shutter_contact2_plus_device(
    device_id: str = "hdm:ZigBee:shuttercontact1",
    name: str = "Shutter contact",
    bypass: BypassService.State = BypassService.State.BYPASS_INACTIVE,
    bypass_infinite: bool = False,
    vibration_enabled: bool = False,
) -> SHCShutterContact2Plus:
    """Build a minimal device double for a vibration-capable Door/Window Contact II Plus."""
    device = create_autospec(SHCShutterContact2Plus, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "SWD2_PLUS"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.bypass = bypass
    device.bypass_infinite = bypass_infinite
    device.enabled = vibration_enabled
    return device


class FakeLatestMotionService:
    """Minimal double of a LatestMotion DeviceService's event-callback API."""

    id = "LatestMotion"

    def __init__(self) -> None:
        """Initialize the fake service's callback registry."""
        self._event_callbacks: dict[str, Any] = {}

    def register_event(self, event: str, callback: Any) -> None:
        """Register a callback for the given device id."""
        self._event_callbacks[event] = callback

    def subscribe_callback(self, entity_id: str, callback: Any) -> None:
        """No-op: SHCEntity subscribes to every device service's generic callback."""

    def unsubscribe_callback(self, entity_id: str) -> None:
        """No-op counterpart to subscribe_callback."""


def motion_detector_device(
    device_id: str = "hdm:HomeMaticIP:motion1",
    name: str = "Motion Detector",
    latestmotion: str = "",
) -> SHCMotionDetector:
    """Build a minimal device double for the motion_detectors bucket."""
    device = create_autospec(SHCMotionDetector, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "MD"
    device.device_services = [FakeLatestMotionService()]
    device.deleted = False
    device.status = "AVAILABLE"
    device.latestmotion = latestmotion
    return device


def motion_detector2_device(
    device_id: str = "hdm:ZigBee:motiondetector1",
    name: str = "Motion Detector",
    pet_immunity_enabled: bool = False,
    tamper_protection_enabled: bool = False,
    supports_smart_sensitivity: bool = False,
    smart_sensitivity_enabled: bool = False,
    latestmotion: str = "",
) -> SHCMotionDetector2:
    """Build a minimal device double for the motion_detectors2 bucket."""
    device = create_autospec(SHCMotionDetector2, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "MD2"
    device.device_services = [FakeLatestMotionService()]
    device.deleted = False
    device.status = "AVAILABLE"
    device.pet_immunity_enabled = pet_immunity_enabled
    device.tamper_protection_enabled = tamper_protection_enabled
    device.supports_smart_sensitivity = supports_smart_sensitivity
    device.smart_sensitivity_enabled = smart_sensitivity_enabled
    device.latestmotion = latestmotion
    return device


def smoke_detector_device(
    device_id: str = "hdm:ZigBee:smokedetector1",
    name: str = "Smoke Detector",
    supports_intrusion_alarm: bool = True,
    intrusion_alarm: bool = False,
) -> SHCSmokeDetector:
    """Build a minimal device double for the smoke_detectors bucket."""
    device = create_autospec(SHCSmokeDetector, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "SMOKE_DETECTOR2"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.supports_intrusion_alarm = supports_intrusion_alarm
    device.intrusion_alarm = intrusion_alarm
    return device


def twinguard_device(
    device_id: str = "hdm:HomeMaticIP:twinguard1",
    name: str = "Twinguard",
    supports_nightly_promise: bool = False,
    nightly_promise_enabled: bool = False,
) -> SHCTwinguard:
    """Build a minimal device double for the twinguards bucket."""
    device = create_autospec(SHCTwinguard, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.manufacturer = "Bosch"
    device.device_model = "TWINGUARD"
    device.device_services = []
    device.deleted = False
    device.status = "AVAILABLE"
    device.supports_nightly_promise = supports_nightly_promise
    device.nightly_promise_enabled = nightly_promise_enabled
    return device

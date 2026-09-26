"""Tests for the Bosch SHC switch platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import (
    BypassService,
    PrivacyModeService,
    SilentModeService,
    ThermostatService,
)
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    camera_outdoor_gen2_device,
    light_switch_bsm_device,
    micromodule_relay_device,
    motion_detector2_device,
    presence_simulation_system_device,
    setup_integration,
    shutter_contact2_device,
    shutter_contact2_plus_device,
    smart_plug_compact_device,
    smart_plug_device,
    smoke_detector_device,
    thermostat_device,
    thermostat_gen2_device,
    twinguard_device,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the switch platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device(child_lock=ThermostatService.State.OFF)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_child_lock(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A thermostat's enum-based child lock is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.thermostats[0]

    state = hass.states.get("switch.thermostat_child_lock")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.thermostat_child_lock"},
        blocking=True,
    )
    assert device.child_lock is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.thermostat_child_lock"},
        blocking=True,
    )
    assert device.child_lock is False


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "thermostats": [
                thermostat_device(
                    supports_silentmode=True,
                    silentmode=SilentModeService.State.MODE_NORMAL,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_silent_mode(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A thermostat's silent mode is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.thermostats[0]

    state = hass.states.get("switch.thermostat_whisper_mode")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.thermostat_whisper_mode"},
        blocking=True,
    )
    assert device.silentmode is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.thermostat_whisper_mode"},
        blocking=True,
    )
    assert device.silentmode is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device(supports_silentmode=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_no_silent_mode_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No switch is created for a thermostat without silent-mode support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.thermostat_whisper_mode") is None


@pytest.mark.parametrize(
    "device_buckets",
    [{"micromodule_relays": [micromodule_relay_device(child_lock=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_relay_child_lock(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A ChildProtection device's bool-based child lock is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_relays[0]

    state = hass.states.get("switch.relay_child_lock")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.relay_child_lock"},
        blocking=True,
    )
    assert device.child_lock is True


@pytest.mark.parametrize(
    "device_buckets",
    [{"light_switches_bsm": [light_switch_bsm_device(child_lock=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_light_switch_bsm_child_lock_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A BSM light switch's primary switch and child-lock switch use distinct unique_ids."""
    await setup_integration(hass, mock_config_entry)

    lightswitch_entry = entity_registry.async_get("switch.light_switch")
    child_lock_entry = entity_registry.async_get("switch.light_switch_child_lock")
    assert lightswitch_entry is not None
    assert child_lock_entry is not None
    assert lightswitch_entry.unique_id != child_lock_entry.unique_id


@pytest.mark.parametrize(
    "device_buckets",
    [{"presence_simulation_system": presence_simulation_system_device(enabled=False)}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_presence_simulation_system(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The presence simulation system is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.presence_simulation_system

    state = hass.states.get("switch.presence_simulation")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.presence_simulation"},
        blocking=True,
    )
    assert device.enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.presence_simulation"},
        blocking=True,
    )
    assert device.enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"presence_simulation_system": presence_simulation_system_device(enabled=False)}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_presence_simulation_system_push_update(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A controller-side push update reaches the switch without polling."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.presence_simulation_system
    service = device.device_services[0]
    on_state_changed = service.subscribe_callback.call_args.args[1]

    device.enabled = True
    on_state_changed()
    await hass.async_block_till_done()

    assert hass.states.get("switch.presence_simulation").state == "on"


@pytest.mark.parametrize(
    "device_buckets",
    [{"presence_simulation_system": None}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_no_presence_simulation_system(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No switch is created when the controller has no presence simulation system."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.presence_simulation") is None


@pytest.mark.parametrize(
    "device_buckets",
    [{"smart_plugs": [smart_plug_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_routing_switch_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The Smart Plug's routing switch is named "Range extension", not "Routing"."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get("switch.smart_plug_range_extension")
    assert entry is not None
    state = hass.states.get("switch.smart_plug_range_extension")
    assert state is not None
    assert state.attributes["friendly_name"] == "Smart Plug Range extension"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "shutter_contacts2": [
                shutter_contact2_device(bypass=BypassService.State.BYPASS_INACTIVE)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact2_bypass(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Door/Window Contact II's alarm bypass is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_contacts2[0]

    state = hass.states.get("switch.shutter_contact_break_function")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.shutter_contact_break_function"},
        blocking=True,
    )
    assert device.bypass is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.shutter_contact_break_function"},
        blocking=True,
    )
    assert device.bypass is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts2": [shutter_contact2_device(bypass_infinite=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact2_bypass_infinite(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Door/Window Contact II's bypass-never-expires option is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_contacts2[0]

    state = hass.states.get("switch.shutter_contact_break_function_never_expires")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.shutter_contact_break_function_never_expires"},
        blocking=True,
    )
    device.set_bypass_configuration.assert_called_once_with(infinite=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.shutter_contact_break_function_never_expires"},
        blocking=True,
    )
    device.set_bypass_configuration.assert_called_with(infinite=False)


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts2": [shutter_contact2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact2_bypass_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Door/Window Contact II's two bypass switches use distinct unique_ids."""
    await setup_integration(hass, mock_config_entry)

    bypass_entry = entity_registry.async_get("switch.shutter_contact_break_function")
    bypass_infinite_entry = entity_registry.async_get(
        "switch.shutter_contact_break_function_never_expires"
    )
    assert bypass_entry is not None
    assert bypass_infinite_entry is not None
    assert bypass_entry.unique_id != bypass_infinite_entry.unique_id


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts2": [shutter_contact2_plus_device(vibration_enabled=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact2_plus_vibration_enabled(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Door/Window Contact II Plus's vibration detection is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_contacts2[0]

    state = hass.states.get("switch.shutter_contact_vibration_detection")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.shutter_contact_vibration_detection"},
        blocking=True,
    )
    assert device.enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.shutter_contact_vibration_detection"},
        blocking=True,
    )
    assert device.enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts2": [shutter_contact2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact2_no_vibration_enabled_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No vibration switch is created for a plain (non-Plus) Door/Window Contact II."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.shutter_contact_vibration_detection") is None


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device(pet_immunity_enabled=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_detector2_pet_immunity(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Motion Detector 2's pet immunity setting is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors2[0]

    state = hass.states.get("switch.motion_detector_pet_immunity")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.motion_detector_pet_immunity"},
        blocking=True,
    )
    assert device.pet_immunity_enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.motion_detector_pet_immunity"},
        blocking=True,
    )
    assert device.pet_immunity_enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device(tamper_protection_enabled=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_detector2_tamper_protection(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Motion Detector 2's tamper protection setting is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors2[0]

    state = hass.states.get("switch.motion_detector_sabotage_detection")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.motion_detector_sabotage_detection"},
        blocking=True,
    )
    assert device.tamper_protection_enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.motion_detector_sabotage_detection"},
        blocking=True,
    )
    assert device.tamper_protection_enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"smoke_detectors": [smoke_detector_device(intrusion_alarm=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smoke_detector_intrusion_alarm(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Smoke Detector II's intrusion alarm is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smoke_detectors[0]

    state = hass.states.get("switch.smoke_detector_intrusion_alarm")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.smoke_detector_intrusion_alarm"},
        blocking=True,
    )
    assert device.intrusion_alarm is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.smoke_detector_intrusion_alarm"},
        blocking=True,
    )
    assert device.intrusion_alarm is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"smoke_detectors": [smoke_detector_device(supports_intrusion_alarm=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smoke_detector_no_intrusion_alarm_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No switch is created for a gen-1 Smoke Detector without intrusion-alarm support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.smoke_detector_intrusion_alarm") is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "twinguards": [
                twinguard_device(
                    supports_nightly_promise=True, nightly_promise_enabled=False
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_twinguard_nightly_promise(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Twinguard's nightly promise (Heartbeat) is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.twinguards[0]

    state = hass.states.get("switch.twinguard_heartbeat")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.twinguard_heartbeat"},
        blocking=True,
    )
    assert device.nightly_promise_enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.twinguard_heartbeat"},
        blocking=True,
    )
    assert device.nightly_promise_enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"twinguards": [twinguard_device(supports_nightly_promise=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_twinguard_no_nightly_promise_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No switch is created for a Twinguard without nightly-promise support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.twinguard_heartbeat") is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "thermostats": [
                thermostat_gen2_device(
                    supports_display_configuration=True,
                    humidity_warning_enabled=False,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_gen2_humidity_warning(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Thermostat Gen2's humidity warning is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.thermostats[0]

    state = hass.states.get("switch.thermostat_gen2_humidity_warning")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.thermostat_gen2_humidity_warning"},
        blocking=True,
    )
    assert device.humidity_warning_enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.thermostat_gen2_humidity_warning"},
        blocking=True,
    )
    assert device.humidity_warning_enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"thermostats": [thermostat_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_thermostat_no_humidity_warning_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No switch is created for a Gen-1 thermostat, which lacks display-configuration support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.thermostat_gen2_humidity_warning") is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "roomthermostats": [
                thermostat_gen2_device(
                    device_id="hdm:ZigBee:roomthermostatgen2_1",
                    name="Room Thermostat 2",
                    supports_display_configuration=True,
                    humidity_warning_enabled=False,
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_roomthermostat_gen2_humidity_warning(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Room Thermostat 2's humidity warning is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.roomthermostats[0]

    state = hass.states.get("switch.room_thermostat_2_humidity_warning")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.room_thermostat_2_humidity_warning"},
        blocking=True,
    )
    assert device.humidity_warning_enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.room_thermostat_2_humidity_warning"},
        blocking=True,
    )
    assert device.humidity_warning_enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs": [
                smart_plug_device(
                    supports_energy_saving_mode=True, energy_saving_mode_enabled=False
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_energy_saving_mode(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Smart Plug's energy saving mode is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smart_plugs[0]

    state = hass.states.get("switch.smart_plug_energy_saving_mode")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.smart_plug_energy_saving_mode"},
        blocking=True,
    )
    assert device.energy_saving_mode_enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.smart_plug_energy_saving_mode"},
        blocking=True,
    )
    assert device.energy_saving_mode_enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [{"smart_plugs": [smart_plug_device(supports_energy_saving_mode=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_no_energy_saving_mode_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No switch is created for a Smart Plug without energy-saving-mode support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.smart_plug_energy_saving_mode") is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "smart_plugs_compact": [
                smart_plug_compact_device(
                    supports_energy_saving_mode=True, energy_saving_mode_enabled=False
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_compact_energy_saving_mode(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Smart Plug Compact's energy saving mode is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smart_plugs_compact[0]

    state = hass.states.get("switch.smart_plug_compact_energy_saving_mode")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.smart_plug_compact_energy_saving_mode"},
        blocking=True,
    )
    assert device.energy_saving_mode_enabled is True


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "motion_detectors2": [
                motion_detector2_device(
                    supports_smart_sensitivity=True, smart_sensitivity_enabled=False
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_detector2_smart_sensitivity(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Motion Detector 2's automatic sensitivity is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors2[0]

    state = hass.states.get("switch.motion_detector_automatic_sensitivity")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.motion_detector_automatic_sensitivity"},
        blocking=True,
    )
    assert device.smart_sensitivity_enabled is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.motion_detector_automatic_sensitivity"},
        blocking=True,
    )
    assert device.smart_sensitivity_enabled is False


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "motion_detectors2": [
                motion_detector2_device(supports_smart_sensitivity=False)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_detector2_no_smart_sensitivity_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No switch is created for a Motion Detector 2 without smart-sensitivity support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.motion_detector_automatic_sensitivity") is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_relays": [
                micromodule_relay_device(
                    supports_switch_configuration=True, swap_inputs=False
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_relay_swap_inputs(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Micromodule Relay's swap-inputs setting is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_relays[0]

    state = hass.states.get("switch.relay_swap_inputs")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.relay_swap_inputs"},
        blocking=True,
    )
    assert device.swap_inputs is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.relay_swap_inputs"},
        blocking=True,
    )
    assert device.swap_inputs is False


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_relays": [
                micromodule_relay_device(
                    supports_switch_configuration=True, swap_outputs=False
                )
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_relay_swap_outputs(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Micromodule Relay's swap-outputs setting is exposed and controllable."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_relays[0]

    state = hass.states.get("switch.relay_swap_outputs")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.relay_swap_outputs"},
        blocking=True,
    )
    assert device.swap_outputs is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.relay_swap_outputs"},
        blocking=True,
    )
    assert device.swap_outputs is False


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_relays": [
                micromodule_relay_device(supports_switch_configuration=False)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_relay_no_switch_configuration_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No swap-inputs/outputs switches are created without switch-configuration support."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.relay_swap_inputs") is None
    assert hass.states.get("switch.relay_swap_outputs") is None


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "camera_outdoor_gen2": [
                camera_outdoor_gen2_device(privacymode=PrivacyModeService.State.ENABLED)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_camera_outdoor_gen2_privacy_mode(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An Outdoor Camera Gen2's privacy mode is exposed and controllable as a switch."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.camera_outdoor_gen2[0]

    state = hass.states.get("switch.outdoor_camera")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.outdoor_camera"},
        blocking=True,
    )
    assert device.privacymode is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.outdoor_camera"},
        blocking=True,
    )
    assert device.privacymode is False

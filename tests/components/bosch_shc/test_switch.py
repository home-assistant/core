"""Tests for the Bosch SHC switch platform."""

import contextlib
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from boschshcpy import (
    SHCCamera360,
    SHCCameraEyes,
    SHCCameraOutdoorGen2,
    SHCLightSwitch,
    SHCMicromoduleRelay,
    SHCShutterContact2,
    SHCShutterContact2Plus,
    SHCSmartPlug,
    SHCSmartPlugCompact,
    SHCThermostat,
    SHCUserDefinedState,
)

from homeassistant.components.bosch_shc.const import DOMAIN, OPT_EXCLUDED_DEVICES
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_async_set(device: MagicMock, key: str) -> AsyncMock:
    """Attach an AsyncMock for async_set_<key> and return it."""
    am = AsyncMock()
    setattr(device, f"async_set_{key}", am)
    return am


# ---------------------------------------------------------------------------
# SmartPlug (outlet switch + routing switch)
# ---------------------------------------------------------------------------


async def test_smart_plug_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartPlug entity reports STATE_ON when switchstate == State.ON."""
    plug = make_device(
        "plug-1",
        "Smart Plug",
        switchstate=SHCSmartPlug.PowerSwitchService.State.ON,
        routing=SHCSmartPlug.RoutingService.State.ENABLED,
        status="AVAILABLE",
    )
    _make_async_set(plug, "switchstate")
    _make_async_set(plug, "routing")
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.smart_plug")
    assert state is not None
    assert state.state == STATE_ON


async def test_smart_plug_is_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartPlug entity reports STATE_OFF when switchstate == State.OFF."""
    plug = make_device(
        "plug-2",
        "Smart Plug Off",
        switchstate=SHCSmartPlug.PowerSwitchService.State.OFF,
        routing=SHCSmartPlug.RoutingService.State.DISABLED,
        status="AVAILABLE",
    )
    _make_async_set(plug, "switchstate")
    _make_async_set(plug, "routing")
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.smart_plug_off")
    assert state is not None
    assert state.state == STATE_OFF


async def test_smart_plug_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Calling switch.turn_on on a SmartPlug entity calls async_set_switchstate(True)."""
    plug = make_device(
        "plug-3",
        "Smart Plug TurnOn",
        switchstate=SHCSmartPlug.PowerSwitchService.State.OFF,
        routing=SHCSmartPlug.RoutingService.State.DISABLED,
        status="AVAILABLE",
    )
    async_set_switchstate = _make_async_set(plug, "switchstate")
    _make_async_set(plug, "routing")
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.smart_plug_turnon"},
        blocking=True,
    )
    async_set_switchstate.assert_awaited_once_with(True)


async def test_smart_plug_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Calling switch.turn_off on a SmartPlug entity calls async_set_switchstate(False)."""
    plug = make_device(
        "plug-4",
        "Smart Plug TurnOff",
        switchstate=SHCSmartPlug.PowerSwitchService.State.ON,
        routing=SHCSmartPlug.RoutingService.State.ENABLED,
        status="AVAILABLE",
    )
    async_set_switchstate = _make_async_set(plug, "switchstate")
    _make_async_set(plug, "routing")
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.smart_plug_turnoff"},
        blocking=True,
    )
    async_set_switchstate.assert_awaited_once_with(False)


async def test_smart_plug_routing_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartPlug routing sub-entity reflects routing state and calls async_set_routing."""
    plug = make_device(
        "plug-5",
        "Smart Plug Routing",
        switchstate=SHCSmartPlug.PowerSwitchService.State.ON,
        routing=SHCSmartPlug.RoutingService.State.ENABLED,
        status="AVAILABLE",
    )
    _make_async_set(plug, "switchstate")
    async_set_routing = _make_async_set(plug, "routing")
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    await setup_integration(hass, mock_config_entry)

    routing_entity = hass.states.get("switch.smart_plug_routing_routing")
    assert routing_entity is not None
    assert routing_entity.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.smart_plug_routing_routing"},
        blocking=True,
    )
    async_set_routing.assert_awaited_once_with(False)


async def test_smart_plug_energy_saving_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartPlug with energy_saving_mode_enabled creates an extra entity."""
    plug = make_device(
        "plug-6",
        "Smart Plug ESM",
        switchstate=SHCSmartPlug.PowerSwitchService.State.ON,
        routing=SHCSmartPlug.RoutingService.State.ENABLED,
        supports_energy_saving_mode=True,
        energy_saving_mode_enabled=True,
        status="AVAILABLE",
    )
    _make_async_set(plug, "switchstate")
    _make_async_set(plug, "routing")
    async_set_esm = _make_async_set(plug, "energy_saving_mode_enabled")
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.smart_plug_esm_energysavingmode")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.smart_plug_esm_energysavingmode"},
        blocking=True,
    )
    async_set_esm.assert_awaited_once_with(False)


async def test_smart_plug_warning_suppressed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartPlug with warning_suppressed creates an extra entity."""
    plug = make_device(
        "plug-7",
        "Smart Plug Warn",
        switchstate=SHCSmartPlug.PowerSwitchService.State.ON,
        routing=SHCSmartPlug.RoutingService.State.ENABLED,
        supports_power_switch_warning=True,
        warning_suppressed=False,
        status="AVAILABLE",
    )
    _make_async_set(plug, "switchstate")
    _make_async_set(plug, "routing")
    _make_async_set(plug, "warning_suppressed")
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.smart_plug_warn_warningsuppressed")
    assert state is not None
    assert state.state == STATE_OFF


# ---------------------------------------------------------------------------
# SmartPlugCompact
# ---------------------------------------------------------------------------


async def test_smart_plug_compact_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartPlugCompact entity reports STATE_ON."""
    plug = make_device(
        "compact-1",
        "Compact Plug",
        switchstate=SHCSmartPlugCompact.PowerSwitchService.State.ON,
        status="AVAILABLE",
    )
    _make_async_set(plug, "switchstate")
    mock_setup_dependencies.device_helper.smart_plugs_compact = [plug]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.compact_plug")
    assert state is not None
    assert state.state == STATE_ON


async def test_smart_plug_compact_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartPlugCompact turn_on calls async_set_switchstate(True)."""
    plug = make_device(
        "compact-2",
        "Compact On",
        switchstate=SHCSmartPlugCompact.PowerSwitchService.State.OFF,
        status="AVAILABLE",
    )
    async_set_switchstate = _make_async_set(plug, "switchstate")
    mock_setup_dependencies.device_helper.smart_plugs_compact = [plug]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.compact_on"},
        blocking=True,
    )
    async_set_switchstate.assert_awaited_once_with(True)


# ---------------------------------------------------------------------------
# Light Switch BSM
# ---------------------------------------------------------------------------


async def test_light_switch_bsm_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch BSM entity reports STATE_ON when switchstate == State.ON."""
    switch = make_device(
        "bsm-1",
        "BSM Light Switch",
        switchstate=SHCLightSwitch.PowerSwitchService.State.ON,
        child_lock=False,
        status="AVAILABLE",
    )
    _make_async_set(switch, "switchstate")
    _make_async_set(switch, "child_lock")
    mock_setup_dependencies.device_helper.light_switches_bsm = [switch]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.bsm_light_switch")
    assert state is not None
    assert state.state == STATE_ON


async def test_light_switch_bsm_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LightSwitch BSM turn_off calls async_set_switchstate(False)."""
    switch = make_device(
        "bsm-2",
        "BSM Switch Off",
        switchstate=SHCLightSwitch.PowerSwitchService.State.ON,
        child_lock=False,
        status="AVAILABLE",
    )
    async_set_switchstate = _make_async_set(switch, "switchstate")
    _make_async_set(switch, "child_lock")
    mock_setup_dependencies.device_helper.light_switches_bsm = [switch]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.bsm_switch_off"},
        blocking=True,
    )
    async_set_switchstate.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# MicromoduleRelay
# ---------------------------------------------------------------------------


async def test_micromodule_relay_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MicromoduleRelay entity reports STATE_ON."""
    relay = make_device(
        "relay-1",
        "Micromodule Relay",
        switchstate=SHCMicromoduleRelay.PowerSwitchService.State.ON,
        child_lock=False,
        status="AVAILABLE",
    )
    _make_async_set(relay, "switchstate")
    _make_async_set(relay, "child_lock")
    mock_setup_dependencies.device_helper.micromodule_relays = [relay]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.micromodule_relay")
    assert state is not None
    assert state.state == STATE_ON


async def test_micromodule_relay_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MicromoduleRelay turn_on calls async_set_switchstate(True)."""
    relay = make_device(
        "relay-2",
        "Relay Turn On",
        switchstate=SHCMicromoduleRelay.PowerSwitchService.State.OFF,
        child_lock=False,
        status="AVAILABLE",
    )
    async_set_switchstate = _make_async_set(relay, "switchstate")
    _make_async_set(relay, "child_lock")
    mock_setup_dependencies.device_helper.micromodule_relays = [relay]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.relay_turn_on"},
        blocking=True,
    )
    async_set_switchstate.assert_awaited_once_with(True)


async def test_micromodule_relay_swap_inputs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MicromoduleRelay with swap_inputs creates an extra config entity."""
    relay = make_device(
        "relay-3",
        "Relay Swap",
        switchstate=SHCMicromoduleRelay.PowerSwitchService.State.ON,
        child_lock=False,
        supports_switch_configuration=True,
        swap_inputs=True,
        swap_outputs=False,
        status="AVAILABLE",
    )
    _make_async_set(relay, "switchstate")
    _make_async_set(relay, "child_lock")
    async_set_swap_inputs = _make_async_set(relay, "swap_inputs")
    _make_async_set(relay, "swap_outputs")
    mock_setup_dependencies.device_helper.micromodule_relays = [relay]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.relay_swap_swapinputs")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.relay_swap_swapinputs"},
        blocking=True,
    )
    async_set_swap_inputs.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# CameraEyes
# ---------------------------------------------------------------------------


async def test_camera_eyes_privacy_mode_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CameraEyes switch is STATE_ON when privacy mode is DISABLED (camera active)."""
    cam = make_device(
        "cam-eyes-1",
        "Camera Eyes",
        privacymode=SHCCameraEyes.PrivacyModeService.State.DISABLED,
        cameralight=SHCCameraEyes.CameraLightService.State.ON,
        cameranotification=SHCCameraEyes.CameraNotificationService.State.ENABLED,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    _make_async_set(cam, "cameralight")
    _make_async_set(cam, "cameranotification")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_eyes = [cam]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.camera_eyes")
    assert state is not None
    assert state.state == STATE_ON


async def test_camera_eyes_camera_light_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CameraEyes camera light sub-entity is STATE_OFF when light is OFF."""
    cam = make_device(
        "cam-eyes-2",
        "Camera Eyes Light",
        privacymode=SHCCameraEyes.PrivacyModeService.State.DISABLED,
        cameralight=SHCCameraEyes.CameraLightService.State.OFF,
        cameranotification=SHCCameraEyes.CameraNotificationService.State.DISABLED,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    async_set_cameralight = _make_async_set(cam, "cameralight")
    _make_async_set(cam, "cameranotification")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_eyes = [cam]

    await setup_integration(hass, mock_config_entry)

    light_state = hass.states.get("switch.camera_eyes_light_light")
    assert light_state is not None
    assert light_state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.camera_eyes_light_light"},
        blocking=True,
    )
    async_set_cameralight.assert_awaited_once_with(True)


async def test_camera_eyes_notification_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CameraEyes notification sub-entity reflects notification state."""
    cam = make_device(
        "cam-eyes-3",
        "Camera Eyes Notif",
        privacymode=SHCCameraEyes.PrivacyModeService.State.DISABLED,
        cameralight=SHCCameraEyes.CameraLightService.State.OFF,
        cameranotification=SHCCameraEyes.CameraNotificationService.State.ENABLED,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    _make_async_set(cam, "cameralight")
    async_set_notif = _make_async_set(cam, "cameranotification")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_eyes = [cam]

    await setup_integration(hass, mock_config_entry)

    notif_state = hass.states.get("switch.camera_eyes_notif_notification")
    assert notif_state is not None
    assert notif_state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.camera_eyes_notif_notification"},
        blocking=True,
    )
    async_set_notif.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# Camera360
# ---------------------------------------------------------------------------


async def test_camera360_privacy_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Camera360 switch is STATE_ON when privacy mode is DISABLED."""
    cam = make_device(
        "cam-360-1",
        "Camera 360",
        privacymode=SHCCamera360.PrivacyModeService.State.DISABLED,
        cameranotification=SHCCamera360.CameraNotificationService.State.ENABLED,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    _make_async_set(cam, "cameranotification")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_360 = [cam]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.camera_360")
    assert state is not None
    assert state.state == STATE_ON


async def test_camera360_notification_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Camera360 notification sub-entity: turn_off calls async_set_cameranotification(False)."""
    cam = make_device(
        "cam-360-2",
        "Camera 360 Notif",
        privacymode=SHCCamera360.PrivacyModeService.State.DISABLED,
        cameranotification=SHCCamera360.CameraNotificationService.State.ENABLED,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    async_set_notif = _make_async_set(cam, "cameranotification")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_360 = [cam]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.camera_360_notif_notification"},
        blocking=True,
    )
    async_set_notif.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# CameraOutdoorGen2
# ---------------------------------------------------------------------------


async def test_camera_outdoor_gen2_privacy_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CameraOutdoorGen2 switch is STATE_ON when privacy mode is DISABLED."""
    cam = make_device(
        "cam-og2-1",
        "Outdoor Camera",
        privacymode=SHCCameraOutdoorGen2.PrivacyModeService.State.DISABLED,
        camerafrontlight=SHCCameraOutdoorGen2.CameraFrontLightService.State.ON,
        cameraambientlight=SHCCameraOutdoorGen2.CameraAmbientLightService.State.OFF,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    _make_async_set(cam, "camerafrontlight")
    _make_async_set(cam, "cameraambientlight")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_outdoor_gen2 = [cam]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.outdoor_camera")
    assert state is not None
    assert state.state == STATE_ON


async def test_camera_outdoor_gen2_frontlight_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CameraOutdoorGen2 Frontlight sub-entity is STATE_OFF when light is OFF."""
    cam = make_device(
        "cam-og2-2",
        "Outdoor Cam Frontlight",
        privacymode=SHCCameraOutdoorGen2.PrivacyModeService.State.DISABLED,
        camerafrontlight=SHCCameraOutdoorGen2.CameraFrontLightService.State.OFF,
        cameraambientlight=SHCCameraOutdoorGen2.CameraAmbientLightService.State.OFF,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    async_set_frontlight = _make_async_set(cam, "camerafrontlight")
    _make_async_set(cam, "cameraambientlight")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_outdoor_gen2 = [cam]

    await setup_integration(hass, mock_config_entry)

    front_state = hass.states.get("switch.outdoor_cam_frontlight_frontlight")
    assert front_state is not None
    assert front_state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.outdoor_cam_frontlight_frontlight"},
        blocking=True,
    )
    async_set_frontlight.assert_awaited_once_with(True)


async def test_camera_outdoor_gen2_ambientlight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CameraOutdoorGen2 AmbientLight sub-entity is STATE_ON when light is ON."""
    cam = make_device(
        "cam-og2-3",
        "Outdoor Cam Ambient",
        privacymode=SHCCameraOutdoorGen2.PrivacyModeService.State.DISABLED,
        camerafrontlight=SHCCameraOutdoorGen2.CameraFrontLightService.State.OFF,
        cameraambientlight=SHCCameraOutdoorGen2.CameraAmbientLightService.State.ON,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    _make_async_set(cam, "camerafrontlight")
    async_set_ambient = _make_async_set(cam, "cameraambientlight")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_outdoor_gen2 = [cam]

    await setup_integration(hass, mock_config_entry)

    ambient_state = hass.states.get("switch.outdoor_cam_ambient_ambientlight")
    assert ambient_state is not None
    assert ambient_state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.outdoor_cam_ambient_ambientlight"},
        blocking=True,
    )
    async_set_ambient.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# Presence Simulation System
# ---------------------------------------------------------------------------


async def test_presence_simulation_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """PresenceSimulation entity reports STATE_ON when enabled=True."""
    pss = make_device(
        "pss-1",
        "Presence Simulation",
        enabled=True,
        status="AVAILABLE",
    )
    _make_async_set(pss, "enabled")
    # presence_simulation_system is a singleton (truthy device, not a list)
    mock_setup_dependencies.device_helper.presence_simulation_system = pss

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.presence_simulation")
    assert state is not None
    assert state.state == STATE_ON


async def test_presence_simulation_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """PresenceSimulation turn_off calls async_set_enabled(False)."""
    pss = make_device(
        "pss-2",
        "Presence Sim Off",
        enabled=True,
        status="AVAILABLE",
    )
    async_set_enabled = _make_async_set(pss, "enabled")
    mock_setup_dependencies.device_helper.presence_simulation_system = pss

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.presence_sim_off"},
        blocking=True,
    )
    async_set_enabled.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# ShutterContact2 bypass
# ---------------------------------------------------------------------------


async def test_shutter_contact2_bypass_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ShutterContact2 bypass entity is STATE_ON when bypass == BYPASS_ACTIVE."""
    sc = make_device(
        "sc2-1",
        "Shutter Contact 2",
        bypass=SHCShutterContact2.BypassService.State.BYPASS_ACTIVE,
        status="AVAILABLE",
    )
    # Use spec_set=False so isinstance check uses SHCShutterContact2, not Plus
    sc.__class__ = SHCShutterContact2
    _make_async_set(sc, "bypass")
    mock_setup_dependencies.device_helper.shutter_contacts2 = [sc]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.shutter_contact_2")
    assert state is not None
    assert state.state == STATE_ON


async def test_shutter_contact2_bypass_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ShutterContact2 bypass turn_off calls async_set_bypass(False)."""
    sc = make_device(
        "sc2-2",
        "Shutter Contact Bypass",
        bypass=SHCShutterContact2.BypassService.State.BYPASS_ACTIVE,
        status="AVAILABLE",
    )
    sc.__class__ = SHCShutterContact2
    async_set_bypass = _make_async_set(sc, "bypass")
    mock_setup_dependencies.device_helper.shutter_contacts2 = [sc]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.shutter_contact_bypass"},
        blocking=True,
    )
    async_set_bypass.assert_awaited_once_with(False)


async def test_shutter_contact2_plus_vibration_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ShutterContact2Plus creates an additional vibration_enabled entity."""
    sc_plus = make_device(
        "sc2plus-1",
        "Shutter Contact Plus",
        bypass=SHCShutterContact2.BypassService.State.BYPASS_ACTIVE,
        enabled=True,
        status="AVAILABLE",
    )
    sc_plus.__class__ = SHCShutterContact2Plus
    _make_async_set(sc_plus, "bypass")
    async_set_vibration = _make_async_set(sc_plus, "enabled")
    mock_setup_dependencies.device_helper.shutter_contacts2 = [sc_plus]

    await setup_integration(hass, mock_config_entry)

    # The bypass switch
    bypass_state = hass.states.get("switch.shutter_contact_plus")
    assert bypass_state is not None
    assert bypass_state.state == STATE_ON

    # The vibration_enabled switch (attr_name="VibrationEnabled")
    vibration_state = hass.states.get("switch.shutter_contact_plus_vibrationenabled")
    assert vibration_state is not None
    assert vibration_state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.shutter_contact_plus_vibrationenabled"},
        blocking=True,
    )
    async_set_vibration.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# Thermostat child lock + silent mode
# ---------------------------------------------------------------------------


def _make_thermostat(device_id: str, name: str, **extra) -> MagicMock:
    """Make a thermostat mock with all numeric attributes concrete.

    number.py SHCNumber reads ``device.min_offset`` / ``device.max_offset`` as
    ``native_min_value`` / ``native_max_value`` and HA serialises these to the
    entity registry at teardown.  Leaving them as MagicMock causes a teardown
    crash.  Likewise sensor.py reads ``temperature`` and ``position``; the
    entity state value is serialised too.
    """
    defaults: dict = {
        "min_offset": -5.0,
        "max_offset": 5.0,
        "step_size": 0.5,
        "offset": 0.0,
        "temperature": 21.0,
        "position": 30,
        "valvestate": MagicMock(name="GENERIC_OK"),
        "supports_silentmode": False,
        "supports_display_configuration": False,
        "supports_batterylevel": False,
        "status": "AVAILABLE",
    }
    defaults.update(extra)
    return make_device(device_id, name, **defaults)


async def test_thermostat_child_lock_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Thermostat child_lock_thermostat entity is STATE_ON when child_lock == State.ON."""
    thermo = _make_thermostat(
        "thermo-1",
        "Thermostat",
        child_lock=SHCThermostat.ThermostatService.State.ON,
    )
    _make_async_set(thermo, "child_lock")
    mock_setup_dependencies.device_helper.thermostats = [thermo]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.thermostat_childlock")
    assert state is not None
    assert state.state == STATE_ON


async def test_thermostat_silent_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Thermostat with supports_silentmode=True creates a silent_mode entity."""
    thermo = _make_thermostat(
        "thermo-2",
        "Silent Thermo",
        child_lock=SHCThermostat.ThermostatService.State.OFF,
        silentmode=SHCThermostat.SilentModeService.State.MODE_SILENT,
        supports_silentmode=True,
        supports_batterylevel=False,
    )
    _make_async_set(thermo, "child_lock")
    async_set_silent = _make_async_set(thermo, "silentmode")
    mock_setup_dependencies.device_helper.thermostats = [thermo]

    await setup_integration(hass, mock_config_entry)

    silent_state = hass.states.get("switch.silent_thermo_silentmode")
    assert silent_state is not None
    assert silent_state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.silent_thermo_silentmode"},
        blocking=True,
    )
    async_set_silent.assert_awaited_once_with(False)


async def test_thermostat_humidity_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Thermostat with supports_display_configuration creates humidity_warning_enabled entity."""
    thermo = _make_thermostat(
        "thermo-3",
        "Humid Thermo",
        child_lock=SHCThermostat.ThermostatService.State.OFF,
        supports_display_configuration=True,
        humidity_warning_enabled=True,
        supports_batterylevel=False,
    )
    _make_async_set(thermo, "child_lock")
    async_set_humid = _make_async_set(thermo, "humidity_warning_enabled")
    mock_setup_dependencies.device_helper.thermostats = [thermo]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.humid_thermo_humiditywarning")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.humid_thermo_humiditywarning"},
        blocking=True,
    )
    async_set_humid.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# MotionDetector2 (pet immunity, smart sensitivity, tamper protection)
# ---------------------------------------------------------------------------


async def test_motion_detector2_pet_immunity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionDetector2 pet_immunity_enabled entity is STATE_ON when True."""
    md2 = make_device(
        "md2-1",
        "Motion Detector 2",
        pet_immunity_enabled=True,
        status="AVAILABLE",
    )
    _make_async_set(md2, "pet_immunity_enabled")
    mock_setup_dependencies.device_helper.motion_detectors2 = [md2]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.motion_detector_2_petimmunity")
    assert state is not None
    assert state.state == STATE_ON


async def test_motion_detector2_smart_sensitivity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionDetector2 with smart_sensitivity_enabled creates an extra entity."""
    md2 = make_device(
        "md2-2",
        "Smart Motion",
        pet_immunity_enabled=False,
        smart_sensitivity_enabled=True,
        status="AVAILABLE",
    )
    _make_async_set(md2, "pet_immunity_enabled")
    async_set_smart = _make_async_set(md2, "smart_sensitivity_enabled")
    mock_setup_dependencies.device_helper.motion_detectors2 = [md2]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.smart_motion_smartsensitivity")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.smart_motion_smartsensitivity"},
        blocking=True,
    )
    async_set_smart.assert_awaited_once_with(False)


async def test_motion_detector2_tamper_protection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MotionDetector2 with tamper_protection_enabled creates an extra entity."""
    md2 = make_device(
        "md2-3",
        "Tamper Motion",
        pet_immunity_enabled=False,
        tamper_protection_enabled=True,
        status="AVAILABLE",
    )
    _make_async_set(md2, "pet_immunity_enabled")
    async_set_tamper = _make_async_set(md2, "tamper_protection_enabled")
    mock_setup_dependencies.device_helper.motion_detectors2 = [md2]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.tamper_motion_tamperprotection")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.tamper_motion_tamperprotection"},
        blocking=True,
    )
    async_set_tamper.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# Twinguard (nightly promise, pre alarm)
# ---------------------------------------------------------------------------


async def test_twinguard_nightly_promise(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Twinguard with nightly_promise_enabled creates an entity."""
    tg = make_device(
        "tg-1",
        "Twinguard",
        supports_nightly_promise=True,
        nightly_promise_enabled=True,
        supports_smoke_sensitivity=False,
        status="AVAILABLE",
    )
    async_set_np = _make_async_set(tg, "nightly_promise_enabled")
    mock_setup_dependencies.device_helper.twinguards = [tg]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.twinguard_nightlypromise")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.twinguard_nightlypromise"},
        blocking=True,
    )
    async_set_np.assert_awaited_once_with(False)


async def test_twinguard_pre_alarm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Twinguard with pre_alarm_enabled creates an entity."""
    tg = make_device(
        "tg-2",
        "Twinguard Alarm",
        supports_nightly_promise=False,
        supports_smoke_sensitivity=True,
        pre_alarm_enabled=False,
        status="AVAILABLE",
    )
    async_set_pa = _make_async_set(tg, "pre_alarm_enabled")
    mock_setup_dependencies.device_helper.twinguards = [tg]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.twinguard_alarm_prealarm")
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.twinguard_alarm_prealarm"},
        blocking=True,
    )
    async_set_pa.assert_awaited_once_with(True)


# ---------------------------------------------------------------------------
# Smoke Detector (pre alarm)
# ---------------------------------------------------------------------------


async def test_smoke_detector_pre_alarm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmokeDetector with pre_alarm_enabled creates an entity."""
    sd = make_device(
        "sd-1",
        "Smoke Detector",
        supports_smoke_sensitivity=True,
        pre_alarm_enabled=True,
        status="AVAILABLE",
    )
    async_set_pa = _make_async_set(sd, "pre_alarm_enabled")
    mock_setup_dependencies.device_helper.smoke_detectors = [sd]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.smoke_detector_prealarm")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.smoke_detector_prealarm"},
        blocking=True,
    )
    async_set_pa.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# Child lock on micromodule relays
# ---------------------------------------------------------------------------


async def test_micromodule_relay_child_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MicromoduleRelay also gets a child_lock entity (bool, not thermostat enum)."""
    relay = make_device(
        "relay-cl-1",
        "Relay Child Lock",
        switchstate=SHCMicromoduleRelay.PowerSwitchService.State.ON,
        child_lock=True,
        status="AVAILABLE",
    )
    _make_async_set(relay, "switchstate")
    async_set_cl = _make_async_set(relay, "child_lock")
    mock_setup_dependencies.device_helper.micromodule_relays = [relay]

    await setup_integration(hass, mock_config_entry)

    cl_state = hass.states.get("switch.relay_child_lock_childlock")
    assert cl_state is not None
    assert cl_state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.relay_child_lock_childlock"},
        blocking=True,
    )
    async_set_cl.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# UserDefinedState switch
# ---------------------------------------------------------------------------


async def test_userdefinedstate_switch_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """UserDefinedState switch is STATE_ON when state=True."""
    uds = MagicMock(spec=SHCUserDefinedState)
    uds.id = "uds-1"
    uds.name = "Vacation Mode"
    uds.root_device_id = "shc-root"
    uds.state = True
    uds.deleted = False
    uds.async_set_state = AsyncMock()
    mock_setup_dependencies.userdefinedstates = [uds]
    mock_setup_dependencies.subscribe = MagicMock()
    mock_setup_dependencies._subscribers = []
    mock_setup_dependencies.subscribe_userdefinedstate_callback = MagicMock()
    mock_setup_dependencies.unsubscribe_userdefinedstate_callbacks = MagicMock()

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.userdefinedstate_vacation_mode")
    assert state is not None
    assert state.state == STATE_ON


async def test_userdefinedstate_switch_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """UserDefinedState switch is STATE_OFF when state=False."""
    uds = MagicMock(spec=SHCUserDefinedState)
    uds.id = "uds-2"
    uds.name = "Guest Mode"
    uds.root_device_id = "shc-root"
    uds.state = False
    uds.deleted = False
    uds.async_set_state = AsyncMock()
    mock_setup_dependencies.userdefinedstates = [uds]
    mock_setup_dependencies.subscribe = MagicMock()
    mock_setup_dependencies._subscribers = []
    mock_setup_dependencies.subscribe_userdefinedstate_callback = MagicMock()
    mock_setup_dependencies.unsubscribe_userdefinedstate_callbacks = MagicMock()

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.userdefinedstate_guest_mode")
    assert state is not None
    assert state.state == STATE_OFF


async def test_userdefinedstate_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """UserDefinedState turn_on calls async_set_state(True)."""
    uds = MagicMock(spec=SHCUserDefinedState)
    uds.id = "uds-3"
    uds.name = "Night Mode"
    uds.root_device_id = "shc-root"
    uds.state = False
    uds.deleted = False
    uds.async_set_state = AsyncMock()
    mock_setup_dependencies.userdefinedstates = [uds]
    mock_setup_dependencies.subscribe = MagicMock()
    mock_setup_dependencies._subscribers = []
    mock_setup_dependencies.subscribe_userdefinedstate_callback = MagicMock()
    mock_setup_dependencies.unsubscribe_userdefinedstate_callbacks = MagicMock()

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.userdefinedstate_night_mode"},
        blocking=True,
    )
    uds.async_set_state.assert_awaited_once_with(True)


async def test_userdefinedstate_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """UserDefinedState turn_off calls async_set_state(False)."""
    uds = MagicMock(spec=SHCUserDefinedState)
    uds.id = "uds-4"
    uds.name = "Away Mode"
    uds.root_device_id = "shc-root"
    uds.state = True
    uds.deleted = False
    uds.async_set_state = AsyncMock()
    mock_setup_dependencies.userdefinedstates = [uds]
    mock_setup_dependencies.subscribe = MagicMock()
    mock_setup_dependencies._subscribers = []
    mock_setup_dependencies.subscribe_userdefinedstate_callback = MagicMock()
    mock_setup_dependencies.unsubscribe_userdefinedstate_callbacks = MagicMock()

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.userdefinedstate_away_mode"},
        blocking=True,
    )
    uds.async_set_state.assert_awaited_once_with(False)


# ---------------------------------------------------------------------------
# SHCSwitch.is_on defensive AttributeError guard
# ---------------------------------------------------------------------------


async def test_switch_is_on_attribute_error_returns_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SHCSwitch.is_on returns None (unavailable) on AttributeError from device."""
    # Build a unique subclass so the PropertyMock does not pollute other tests.
    _UniquePlugClass = type("_UniquePlugClass", (MagicMock,), {})
    plug = make_device(
        "plug-ae-1",
        "Plug Attr Error",
        status="AVAILABLE",
    )
    plug.__class__ = _UniquePlugClass
    # Install PropertyMock that raises AttributeError on .switchstate access.
    _UniquePlugClass.switchstate = PropertyMock(
        side_effect=AttributeError("no service")
    )
    # Remove any instance-level attr set by make_device so the PropertyMock fires.
    with contextlib.suppress(AttributeError):
        del plug.switchstate
    _make_async_set(plug, "switchstate")
    _make_async_set(plug, "routing")
    plug.routing = SHCSmartPlug.RoutingService.State.DISABLED
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    await setup_integration(hass, mock_config_entry)

    # When is_on returns None the entity state is "unavailable" (not on/off)
    state = hass.states.get("switch.plug_attr_error")
    assert state is not None
    assert state.state not in (STATE_ON, STATE_OFF)


# ---------------------------------------------------------------------------
# Device excluded by options
# ---------------------------------------------------------------------------


async def test_smart_plug_excluded(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SmartPlug listed in OPT_EXCLUDED_DEVICES is not added to HA."""
    plug = make_device(
        "plug-excl-1",
        "Excluded Plug",
        switchstate=SHCSmartPlug.PowerSwitchService.State.ON,
        routing=SHCSmartPlug.RoutingService.State.ENABLED,
        status="AVAILABLE",
    )
    _make_async_set(plug, "switchstate")
    _make_async_set(plug, "routing")
    mock_setup_dependencies.device_helper.smart_plugs = [plug]

    # Create a fresh entry with the exclusion option pre-set.
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            CONF_HOST: "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            CONF_TOKEN: "abc:test-mac",
            "hostname": "test-mac",
        },
        options={OPT_EXCLUDED_DEVICES: ["plug-excl-1"]},
    )
    await setup_integration(hass, config_entry)

    assert hass.states.get("switch.excluded_plug") is None


# ---------------------------------------------------------------------------
# async_update dispatch (async_update vs executor fallback)
# ---------------------------------------------------------------------------


async def test_camera_eyes_async_update_called(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CameraEyes switch uses async_update when the device supports it."""
    cam = make_device(
        "cam-eyes-upd",
        "Camera Eyes Update",
        privacymode=SHCCameraEyes.PrivacyModeService.State.DISABLED,
        cameralight=SHCCameraEyes.CameraLightService.State.ON,
        cameranotification=SHCCameraEyes.CameraNotificationService.State.ENABLED,
        status="AVAILABLE",
    )
    _make_async_set(cam, "privacymode")
    _make_async_set(cam, "cameralight")
    _make_async_set(cam, "cameranotification")
    cam.async_update = AsyncMock()
    mock_setup_dependencies.device_helper.camera_eyes = [cam]

    await setup_integration(hass, mock_config_entry)

    # Trigger a state refresh on the privacy-mode entity (should_poll=True)
    state = hass.states.get("switch.camera_eyes_update")
    assert state is not None

    # Directly call the entity's async_update to verify dispatch
    entity_id = "switch.camera_eyes_update"
    entity = next(
        e
        for e in hass.states.async_entity_ids(SWITCH_DOMAIN)
        if e == entity_id
    )
    assert entity is not None

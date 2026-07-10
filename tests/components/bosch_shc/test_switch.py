"""Tests for the Bosch SHC switch platform."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from boschshcpy import (
    SHCCamera360,
    SHCCameraEyes,
    SHCLightSwitch,
    SHCSmartPlug,
    SHCSmartPlugCompact,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SCAN_INTERVAL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import setup_integration

from tests.common import async_fire_time_changed, snapshot_platform

SMART_PLUG_ON = SHCSmartPlug.PowerSwitchService.State.ON
SMART_PLUG_OFF = SHCSmartPlug.PowerSwitchService.State.OFF
LIGHT_SWITCH_OFF = SHCLightSwitch.PowerSwitchService.State.OFF
SMART_PLUG_COMPACT_OFF = SHCSmartPlugCompact.PowerSwitchService.State.OFF
CAMERA_EYES_OFF = SHCCameraEyes.CameraLightService.State.OFF
PRIVACY_ENABLED = SHCCamera360.PrivacyModeService.State.ENABLED

SMART_PLUG_ENTITY_ID = "switch.smart_plug"
SMART_PLUG_ROUTING_ENTITY_ID = "switch.smart_plug_routing"
CAMERA_EYES_ENTITY_ID = "switch.camera_eyes"


def _base_device(device_id: str, name: str, **extra: Any) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        id=device_id,
        root_device_id="test-mac",
        serial=f"serial-{device_id}",
        device_services=[],
        manufacturer="Bosch",
        device_model="TEST",
        status="AVAILABLE",
        deleted=False,
        update=MagicMock(),
        subscribe_callback=MagicMock(),
        unsubscribe_callback=MagicMock(),
        **extra,
    )


def _smart_plug_device(
    device_id: str = "hdm:HomeMaticIP:plug1",
    switchstate: SHCSmartPlug.PowerSwitchService.State = SMART_PLUG_OFF,
    routing: str = "ENABLED",
) -> SimpleNamespace:
    return _base_device(
        device_id,
        "Smart Plug",
        switchstate=switchstate,
        routing=SimpleNamespace(name=routing),
    )


def _light_switch_device(
    device_id: str = "hdm:HomeMaticIP:lightswitch1",
    switchstate: SHCLightSwitch.PowerSwitchService.State = LIGHT_SWITCH_OFF,
) -> SimpleNamespace:
    return _base_device(device_id, "Light Switch", switchstate=switchstate)


def _smart_plug_compact_device(
    device_id: str = "hdm:HomeMaticIP:plugcompact1",
    switchstate: SHCSmartPlugCompact.PowerSwitchService.State = SMART_PLUG_COMPACT_OFF,
) -> SimpleNamespace:
    return _base_device(device_id, "Smart Plug Compact", switchstate=switchstate)


def _camera_eyes_device(
    device_id: str = "hdm:HomeMaticIP:cameraeyes1",
    cameralight: SHCCameraEyes.CameraLightService.State = CAMERA_EYES_OFF,
) -> SimpleNamespace:
    return _base_device(device_id, "Camera Eyes", cameralight=cameralight)


def _camera_360_device(
    device_id: str = "hdm:HomeMaticIP:camera3601",
    privacymode: SHCCamera360.PrivacyModeService.State = PRIVACY_ENABLED,
) -> SimpleNamespace:
    return _base_device(device_id, "Camera 360", privacymode=privacymode)


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every switch entity the platform can create, across all 5 buckets."""
    entry = await setup_integration(
        hass,
        [Platform.SWITCH],
        smart_plugs=[_smart_plug_device()],
        light_switches_bsm=[_light_switch_device()],
        smart_plugs_compact=[_smart_plug_compact_device()],
        camera_eyes=[_camera_eyes_device()],
        camera_360=[_camera_360_device()],
    )

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_setup_no_devices_adds_nothing(hass: HomeAssistant) -> None:
    """No devices in any bucket means no switch entities are created."""
    await setup_integration(hass, [Platform.SWITCH])

    assert hass.states.async_all(SWITCH_DOMAIN) == []


@pytest.mark.parametrize(
    ("switchstate", "expected_ha_state"),
    [
        pytest.param(SMART_PLUG_ON, STATE_ON, id="on"),
        pytest.param(SMART_PLUG_OFF, STATE_OFF, id="off"),
    ],
)
async def test_smart_plug_is_on(
    hass: HomeAssistant,
    switchstate: SHCSmartPlug.PowerSwitchService.State,
    expected_ha_state: str,
) -> None:
    """The switch reflects the device's switchstate."""
    device = _smart_plug_device(switchstate=switchstate)
    await setup_integration(hass, [Platform.SWITCH], smart_plugs=[device])

    assert hass.states.get(SMART_PLUG_ENTITY_ID).state == expected_ha_state


@pytest.mark.parametrize(
    ("service", "initial_switchstate", "expected_switchstate"),
    [
        pytest.param(SERVICE_TURN_ON, SMART_PLUG_OFF, True, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, SMART_PLUG_ON, False, id="turn_off"),
    ],
)
async def test_turn_on_off_sets_on_key(
    hass: HomeAssistant,
    service: str,
    initial_switchstate: SHCSmartPlug.PowerSwitchService.State,
    expected_switchstate: bool,
) -> None:
    """turn_on/turn_off set the description's on_key attribute to True/False."""
    device = _smart_plug_device(switchstate=initial_switchstate)
    await setup_integration(hass, [Platform.SWITCH], smart_plugs=[device])

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: SMART_PLUG_ENTITY_ID},
        blocking=True,
    )

    assert device.switchstate is expected_switchstate


async def test_camera_eyes_update_entity_calls_device_update(
    hass: HomeAssistant,
) -> None:
    """The should_poll=True camera_eyes switch calls device.update() on its next scheduled poll."""
    device = _camera_eyes_device()
    await setup_integration(hass, [Platform.SWITCH], camera_eyes=[device])

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    device.update.assert_called()


@pytest.mark.parametrize(
    ("routing", "expected_ha_state"),
    [
        pytest.param("ENABLED", STATE_ON, id="enabled"),
        pytest.param("DISABLED", STATE_OFF, id="disabled"),
    ],
)
async def test_routing_switch_is_on(
    hass: HomeAssistant, routing: str, expected_ha_state: str
) -> None:
    """The routing switch reflects the device's routing.name."""
    device = _smart_plug_device(routing=routing)
    await setup_integration(hass, [Platform.SWITCH], smart_plugs=[device])

    assert hass.states.get(SMART_PLUG_ROUTING_ENTITY_ID).state == expected_ha_state


async def test_routing_switch_turn_on_and_off(hass: HomeAssistant) -> None:
    """turn_on/turn_off on the routing switch set device.routing to a bool."""
    device = _smart_plug_device()
    await setup_integration(hass, [Platform.SWITCH], smart_plugs=[device])

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SMART_PLUG_ROUTING_ENTITY_ID},
        blocking=True,
    )
    assert device.routing is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SMART_PLUG_ROUTING_ENTITY_ID},
        blocking=True,
    )
    assert device.routing is False

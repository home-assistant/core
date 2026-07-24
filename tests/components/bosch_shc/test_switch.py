"""Tests for the Bosch SHC switch platform."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

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

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SMART_PLUG_ON = SHCSmartPlug.PowerSwitchService.State.ON
SMART_PLUG_OFF = SHCSmartPlug.PowerSwitchService.State.OFF
LIGHT_SWITCH_OFF = SHCLightSwitch.PowerSwitchService.State.OFF
SMART_PLUG_COMPACT_OFF = SHCSmartPlugCompact.PowerSwitchService.State.OFF
CAMERA_EYES_OFF = SHCCameraEyes.CameraLightService.State.OFF
PRIVACY_ENABLED = SHCCamera360.PrivacyModeService.State.ENABLED

SMART_PLUG_ENTITY_ID = "switch.smart_plug"
SMART_PLUG_ROUTING_ENTITY_ID = "switch.smart_plug_routing"
CAMERA_EYES_ENTITY_ID = "switch.camera_eyes"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the switch platform.

    Several device_helper buckets used here (smart_plugs, light_switches_bsm,
    smart_plugs_compact) are also read by the sensor platform, which would
    otherwise build power/energy sensors against these plain SimpleNamespace
    doubles and log AttributeError noise for attributes they don't define.
    """
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SWITCH]):
        yield


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


@pytest.mark.parametrize(
    "device_buckets",
    [
        pytest.param(
            {
                "smart_plugs": [_smart_plug_device()],
                "light_switches_bsm": [_light_switch_device()],
                "smart_plugs_compact": [_smart_plug_compact_device()],
                "camera_eyes": [_camera_eyes_device()],
                "camera_360": [_camera_360_device()],
            },
            id="entities",
        )
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot every switch entity the platform can create, across all 5 buckets."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_session")
async def test_setup_no_devices_adds_nothing(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """No devices in any bucket means no switch entities are created."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_all(SWITCH_DOMAIN) == []


@pytest.mark.parametrize(
    ("device_buckets", "expected_ha_state"),
    [
        pytest.param(
            {"smart_plugs": [_smart_plug_device(switchstate=SMART_PLUG_ON)]},
            STATE_ON,
            id="on",
        ),
        pytest.param(
            {"smart_plugs": [_smart_plug_device(switchstate=SMART_PLUG_OFF)]},
            STATE_OFF,
            id="off",
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_smart_plug_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_ha_state: str,
) -> None:
    """The switch reflects the device's switchstate."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(SMART_PLUG_ENTITY_ID)) is not None
    assert state.state == expected_ha_state


@pytest.mark.parametrize(
    ("device_buckets", "service", "expected_switchstate"),
    [
        pytest.param(
            {"smart_plugs": [_smart_plug_device(switchstate=SMART_PLUG_OFF)]},
            SERVICE_TURN_ON,
            True,
            id="turn_on",
        ),
        pytest.param(
            {"smart_plugs": [_smart_plug_device(switchstate=SMART_PLUG_ON)]},
            SERVICE_TURN_OFF,
            False,
            id="turn_off",
        ),
    ],
    indirect=["device_buckets"],
)
async def test_turn_on_off_sets_on_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    service: str,
    expected_switchstate: bool,
) -> None:
    """turn_on/turn_off set the description's on_key attribute to True/False."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smart_plugs[0]

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: SMART_PLUG_ENTITY_ID},
        blocking=True,
    )

    assert device.switchstate is expected_switchstate


@pytest.mark.parametrize(
    "device_buckets",
    [{"camera_eyes": [_camera_eyes_device()]}],
    indirect=True,
)
async def test_camera_eyes_update_entity_calls_device_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """The should_poll=True camera_eyes switch calls device.update() on its next scheduled poll."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.camera_eyes[0]

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)

    device.update.assert_called()


@pytest.mark.parametrize(
    ("device_buckets", "expected_ha_state"),
    [
        pytest.param(
            {"smart_plugs": [_smart_plug_device(routing="ENABLED")]},
            STATE_ON,
            id="enabled",
        ),
        pytest.param(
            {"smart_plugs": [_smart_plug_device(routing="DISABLED")]},
            STATE_OFF,
            id="disabled",
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_routing_switch_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_ha_state: str,
) -> None:
    """The routing switch reflects the device's routing.name."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(SMART_PLUG_ROUTING_ENTITY_ID)) is not None
    assert state.state == expected_ha_state


@pytest.mark.parametrize(
    "device_buckets",
    [{"smart_plugs": [_smart_plug_device()]}],
    indirect=True,
)
async def test_routing_switch_turn_on_and_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """turn_on/turn_off on the routing switch set device.routing to a bool."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smart_plugs[0]

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

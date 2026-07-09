"""Tests for the Bosch SHC switch platform."""

from __future__ import annotations

from collections.abc import Callable
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

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry

SMART_PLUG_ON = SHCSmartPlug.PowerSwitchService.State.ON
SMART_PLUG_OFF = SHCSmartPlug.PowerSwitchService.State.OFF
LIGHT_SWITCH_OFF = SHCLightSwitch.PowerSwitchService.State.OFF
SMART_PLUG_COMPACT_OFF = SHCSmartPlugCompact.PowerSwitchService.State.OFF
CAMERA_EYES_OFF = SHCCameraEyes.CameraLightService.State.OFF
PRIVACY_ENABLED = SHCCamera360.PrivacyModeService.State.ENABLED

# Every device_helper bucket the switch platform itself iterates over
# (smart_plugs, light_switches_bsm, smart_plugs_compact, camera_eyes,
# camera_360), defaulted to empty so a test only creates entities for the
# bucket(s) it explicitly passes.
_EMPTY_DEVICE_BUCKETS: dict[str, list[Any]] = {
    bucket: []
    for bucket in (
        "smart_plugs",
        "light_switches_bsm",
        "smart_plugs_compact",
        "camera_eyes",
        "camera_360",
    )
}


def _base_device(device_id: str, **extra: Any) -> SimpleNamespace:
    return SimpleNamespace(
        name="Test Device",
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
        device_id, switchstate=switchstate, routing=SimpleNamespace(name=routing)
    )


def _light_switch_device(
    device_id: str = "hdm:HomeMaticIP:lightswitch1",
    switchstate: SHCLightSwitch.PowerSwitchService.State = LIGHT_SWITCH_OFF,
) -> SimpleNamespace:
    return _base_device(device_id, switchstate=switchstate)


def _smart_plug_compact_device(
    device_id: str = "hdm:HomeMaticIP:plugcompact1",
    switchstate: SHCSmartPlugCompact.PowerSwitchService.State = SMART_PLUG_COMPACT_OFF,
) -> SimpleNamespace:
    return _base_device(device_id, switchstate=switchstate)


def _camera_eyes_device(
    device_id: str = "hdm:HomeMaticIP:cameraeyes1",
    cameralight: SHCCameraEyes.CameraLightService.State = CAMERA_EYES_OFF,
) -> SimpleNamespace:
    return _base_device(device_id, cameralight=cameralight)


def _camera_360_device(
    device_id: str = "hdm:HomeMaticIP:camera3601",
    privacymode: SHCCamera360.PrivacyModeService.State = PRIVACY_ENABLED,
) -> SimpleNamespace:
    return _base_device(device_id, privacymode=privacymode)


async def _setup_switch_integration(
    hass: HomeAssistant, **device_buckets: list[SimpleNamespace]
) -> MockConfigEntry:
    """Set up bosch_shc with the given device_helper buckets, via a mocked session."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )
    entry.add_to_hass(hass)

    mock_session = MagicMock()
    mock_session.information.unique_id = "test-mac"
    mock_session.information.updateState.name = "UP_TO_DATE"
    mock_session.information.version = "2.0"
    mock_session.device_helper = SimpleNamespace(
        **{**_EMPTY_DEVICE_BUCKETS, **device_buckets}
    )

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession", return_value=mock_session
        ),
        patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_smart_plug_creates_switch_and_routing_switch(
    hass: HomeAssistant,
) -> None:
    """A smart_plugs device yields both an outlet switch and a routing switch."""
    device = _smart_plug_device()
    await _setup_switch_integration(hass, smart_plugs=[device])

    states = hass.states.async_all(SWITCH_DOMAIN)
    assert len(states) == 2

    outlet_state = next(
        s for s in states if s.attributes.get("device_class") == "outlet"
    )
    assert outlet_state is not None

    routing_state = next(s for s in states if s != outlet_state)
    assert routing_state.entity_id.endswith("_routing")


@pytest.mark.parametrize(
    ("device_factory", "bucket", "expected_device_class"),
    [
        pytest.param(
            _light_switch_device,
            "light_switches_bsm",
            "switch",
            id="light_switches_bsm",
        ),
        pytest.param(
            _smart_plug_compact_device,
            "smart_plugs_compact",
            "outlet",
            id="smart_plugs_compact",
        ),
        pytest.param(_camera_eyes_device, "camera_eyes", "switch", id="camera_eyes"),
        pytest.param(_camera_360_device, "camera_360", "switch", id="camera_360"),
    ],
)
async def test_single_bucket_creates_only_switch(
    hass: HomeAssistant,
    device_factory: Callable[[], SimpleNamespace],
    bucket: str,
    expected_device_class: str,
) -> None:
    """These buckets yield only a single switch, no routing switch."""
    device = device_factory()
    await _setup_switch_integration(hass, **{bucket: [device]})

    states = hass.states.async_all(SWITCH_DOMAIN)
    assert len(states) == 1
    assert states[0].attributes["device_class"] == expected_device_class


async def test_setup_no_devices_adds_nothing(hass: HomeAssistant) -> None:
    """No devices in any bucket means no switch entities are created."""
    await _setup_switch_integration(hass)

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
    await _setup_switch_integration(hass, smart_plugs=[device])

    outlet_state = next(
        s
        for s in hass.states.async_all(SWITCH_DOMAIN)
        if s.attributes.get("device_class") == "outlet"
    )
    assert outlet_state.state == expected_ha_state


async def test_turn_on_sets_on_key_true(hass: HomeAssistant) -> None:
    """turn_on sets the description's on_key attribute to True."""
    device = _smart_plug_device(switchstate=SMART_PLUG_OFF)
    await _setup_switch_integration(hass, smart_plugs=[device])

    outlet_state = next(
        s
        for s in hass.states.async_all(SWITCH_DOMAIN)
        if s.attributes.get("device_class") == "outlet"
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: outlet_state.entity_id},
        blocking=True,
    )

    assert device.switchstate is True


async def test_turn_off_sets_on_key_false(hass: HomeAssistant) -> None:
    """turn_off sets the description's on_key attribute to False."""
    device = _smart_plug_device(switchstate=SMART_PLUG_ON)
    await _setup_switch_integration(hass, smart_plugs=[device])

    outlet_state = next(
        s
        for s in hass.states.async_all(SWITCH_DOMAIN)
        if s.attributes.get("device_class") == "outlet"
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: outlet_state.entity_id},
        blocking=True,
    )

    assert device.switchstate is False


async def test_camera_eyes_update_entity_calls_device_update(
    hass: HomeAssistant,
) -> None:
    """The should_poll=True camera_eyes switch calls device.update() when refreshed."""
    device = _camera_eyes_device()
    await _setup_switch_integration(hass, camera_eyes=[device])

    state = hass.states.get(
        next(
            s.entity_id
            for s in hass.states.async_all(SWITCH_DOMAIN)
            if s.attributes.get("device_class") == "switch"
        )
    )
    assert state is not None

    await async_update_entity(hass, state.entity_id)

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
    await _setup_switch_integration(hass, smart_plugs=[device])

    routing_state = next(
        s
        for s in hass.states.async_all(SWITCH_DOMAIN)
        if s.entity_id.endswith("_routing")
    )
    assert routing_state.state == expected_ha_state


async def test_routing_switch_turn_on_and_off(hass: HomeAssistant) -> None:
    """turn_on/turn_off on the routing switch set device.routing to a bool."""
    device = _smart_plug_device()
    await _setup_switch_integration(hass, smart_plugs=[device])

    routing_state = next(
        s
        for s in hass.states.async_all(SWITCH_DOMAIN)
        if s.entity_id.endswith("_routing")
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: routing_state.entity_id},
        blocking=True,
    )
    assert device.routing is True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: routing_state.entity_id},
        blocking=True,
    )
    assert device.routing is False

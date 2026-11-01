"""Test ZHA valve."""

from collections.abc import Callable, Coroutine, Generator
from unittest.mock import patch

import pytest
from zha.application.platforms import ENTITY_REGISTRY, ClusterMatch
from zha.application.platforms.valve import BaseValve
from zha.application.platforms.valve.const import (
    ValveDeviceClass as ZHAValveDeviceClass,
    ValveEntityFeature as ZHAValveEntityFeature,
)
from zha.exceptions import ZHAException
from zigpy.const import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE
from zigpy.device import ZigbeeDevice
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as VALVE_DOMAIN,
    ValveDeviceClass,
    ValveEntityFeature,
    ValveState,
)
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_VALVE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import find_entity_id


class FakeValve(BaseValve):
    """Valve entity that only opens and closes."""

    _unique_id_suffix = "fake"
    _attr_device_class = ZHAValveDeviceClass.WATER
    _cluster_match = ClusterMatch(
        server_clusters=frozenset({general.OnOff.cluster_id}),
    )

    _closed: bool | None = None

    @property
    def is_closed(self) -> bool | None:
        """Return if the valve is closed."""
        return self._closed

    async def async_open_valve(self) -> None:
        """Open the valve."""
        self._closed = False
        self.maybe_emit_state_changed_event()

    async def async_close_valve(self) -> None:
        """Close the valve."""
        self._closed = True
        self.maybe_emit_state_changed_event()


class FakeGasValve(FakeValve):
    """Valve entity with a different device class."""

    _attr_device_class = ZHAValveDeviceClass.GAS


class FakeNoDeviceClassValve(FakeValve):
    """Valve entity without a device class."""

    _attr_device_class = None


class FakePositionValve(FakeValve):
    """Valve entity that reports, sets and stops its position."""

    _attr_reports_position = True
    _attr_supported_features = (
        ZHAValveEntityFeature.OPEN
        | ZHAValveEntityFeature.CLOSE
        | ZHAValveEntityFeature.SET_POSITION
        | ZHAValveEntityFeature.STOP
    )

    _position: int | None = None
    _target: int | None = None

    @property
    def current_valve_position(self) -> int | None:
        """Return the current position of the valve."""
        return self._position

    @property
    def is_opening(self) -> bool | None:
        """Return if the valve is opening."""
        return self._target is not None and self._target > (self._position or 0)

    @property
    def is_closing(self) -> bool | None:
        """Return if the valve is closing."""
        return self._target is not None and self._target < (self._position or 0)

    async def async_set_valve_position(self, position: int) -> None:
        """Start moving the valve to a specific position."""
        self._target = position
        self.maybe_emit_state_changed_event()

    async def async_stop_valve(self) -> None:
        """Stop the valve halfway to its target."""
        assert self._target is not None
        self._position = ((self._position or 0) + self._target) // 2
        self._target = None
        self.maybe_emit_state_changed_event()


class FakeFailingValve(FakeValve):
    """Valve entity whose commands fail."""

    async def async_open_valve(self) -> None:
        """Fail to open the valve."""
        raise ZHAException("Failed to open valve")


@pytest.fixture(autouse=True)
def valve_platform_only() -> Generator[None]:
    """Only set up the valve and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (Platform.SENSOR, Platform.VALVE),
    ):
        yield


@pytest.fixture
def valve_class() -> type[FakeValve]:
    """Return the fake valve entity class to discover."""
    return FakeValve


@pytest.fixture(autouse=True)
def register_fake_valve(valve_class: type[FakeValve]) -> Generator[None]:
    """Make zha discover the fake valve entity on the OnOff server cluster."""
    with patch.dict(
        ENTITY_REGISTRY,
        {
            general.OnOff.cluster_id: [
                *ENTITY_REGISTRY[general.OnOff.cluster_id],
                valve_class,
            ]
        },
    ):
        yield


async def _setup_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> str:
    """Join a device with an OnOff server cluster, return its valve entity ID."""
    await setup_zha()

    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_PROFILE: zha.PROFILE_ID,
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_OUTPUT,
                SIG_EP_INPUT: [general.Basic.cluster_id, general.OnOff.cluster_id],
                SIG_EP_OUTPUT: [],
            }
        },
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.VALVE, zha_device_proxy, hass)
    assert entity_id is not None

    return entity_id


@pytest.mark.parametrize(
    ("valve_class", "device_class"),
    [
        pytest.param(FakeValve, ValveDeviceClass.WATER, id="water"),
        pytest.param(FakeGasValve, ValveDeviceClass.GAS, id="gas"),
        pytest.param(FakeNoDeviceClassValve, None, id="no_device_class"),
    ],
)
async def test_valve_entity(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
    device_class: ValveDeviceClass | None,
) -> None:
    """Test ZHA valve entity is created with the capabilities of the zha entity."""
    entity_id = await _setup_device(hass, setup_zha, zigpy_device_mock)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    )
    assert ATTR_CURRENT_POSITION not in state.attributes


async def test_valve_open_close(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test opening and closing a valve that does not report its position."""
    entity_id = await _setup_device(hass, setup_zha, zigpy_device_mock)

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == ValveState.CLOSED

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == ValveState.OPEN


@pytest.mark.parametrize("valve_class", [FakePositionValve])
async def test_valve_position(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test moving and stopping a valve that reports its position."""
    entity_id = await _setup_device(hass, setup_zha, zigpy_device_mock)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        ValveEntityFeature.OPEN
        | ValveEntityFeature.CLOSE
        | ValveEntityFeature.SET_POSITION
        | ValveEntityFeature.STOP
    )
    assert state.attributes[ATTR_CURRENT_POSITION] is None

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 80},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == ValveState.OPENING

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_STOP_VALVE, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    state = hass.states.get(entity_id)
    assert state.state == ValveState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 40

    # Opening a positional valve moves it to 100
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == ValveState.OPENING

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_STOP_VALVE, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 70

    # Closing a positional valve moves it to 0
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == ValveState.CLOSING


@pytest.mark.parametrize("valve_class", [FakeFailingValve])
async def test_valve_command_failure(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test ZHA errors are raised as Home Assistant errors."""
    entity_id = await _setup_device(hass, setup_zha, zigpy_device_mock)

    with pytest.raises(HomeAssistantError, match="Failed to open valve"):
        await hass.services.async_call(
            VALVE_DOMAIN,
            SERVICE_OPEN_VALVE,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

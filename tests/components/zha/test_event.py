"""Test ZHA event."""

from collections.abc import Callable, Coroutine, Generator
from typing import Any
from unittest.mock import patch

import pytest
from zha.application.platforms import ENTITY_REGISTRY, ClusterMatch
from zha.application.platforms.event import BaseEvent, EntityEventTriggeredEvent
from zha.application.platforms.event.const import (
    ATTR_MULTI_PRESS_COUNT,
    ButtonEventType,
    EventDeviceClass as ZHAEventDeviceClass,
)
from zigpy.const import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    EventDeviceClass,
)
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .common import find_entity_id

from tests.common import mock_restore_cache_with_extra_data

ENTITY_ID = "event.fakemanufacturer_fakemodel_button"


class FakeEvent(BaseEvent):
    """Event entity that can be triggered from tests."""

    _unique_id_suffix = "fake"
    _attr_fallback_name = "Fake"
    _attr_device_class = ZHAEventDeviceClass.BUTTON
    _attr_event_types = [ButtonEventType.PRESS_END, ButtonEventType.MULTI_PRESS_END]
    _cluster_match = ClusterMatch(
        client_clusters=frozenset({general.OnOff.cluster_id}),
    )

    def trigger(
        self, event_type: str, event_attributes: dict[str, Any] | None = None
    ) -> None:
        """Trigger an event, as a concrete subclass would."""
        self._trigger_event(event_type, event_attributes)


class FakeMotionEvent(FakeEvent):
    """Event entity with a different device class."""

    _attr_device_class = ZHAEventDeviceClass.MOTION


class FakeNoDeviceClassEvent(FakeEvent):
    """Event entity without a device class."""

    _attr_device_class = None


@pytest.fixture(autouse=True)
def event_platform_only() -> Generator[None]:
    """Only set up the event and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (Platform.BINARY_SENSOR, Platform.EVENT, Platform.SENSOR),
    ):
        yield


@pytest.fixture
def speed_up_radio_mgr() -> Generator[None]:
    """Speed up the radio manager connection time by removing delays.

    This fixture replaces the fixture in conftest.py by patching the connect
    and shutdown delays to 0 to allow waiting for the patched delays when
    running tests with time frozen, which otherwise blocks forever.
    """
    with (
        patch("homeassistant.components.zha.radio_manager.CONNECT_DELAY_S", 0),
        patch("zha.application.gateway.SHUT_DOWN_DELAY_S", 0),
    ):
        yield


@pytest.fixture
def event_class() -> type[FakeEvent]:
    """Return the fake event entity class to discover."""
    return FakeEvent


@pytest.fixture(autouse=True)
def register_fake_event(event_class: type[FakeEvent]) -> Generator[None]:
    """Make zha discover the fake event entity on the OnOff client cluster."""
    with patch.dict(
        ENTITY_REGISTRY,
        {
            general.OnOff.cluster_id: [
                *ENTITY_REGISTRY[general.OnOff.cluster_id],
                event_class,
            ]
        },
    ):
        yield


async def _setup_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> tuple[str, FakeEvent]:
    """Join a remote with an OnOff client cluster, return its event entity."""
    await setup_zha()

    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_PROFILE: zha.PROFILE_ID,
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_INPUT: [general.Basic.cluster_id],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.EVENT, zha_device_proxy, hass)
    assert entity_id is not None

    zha_entity = next(
        entity
        for entity in zha_device_proxy.device.platform_entities.values()
        if isinstance(entity, FakeEvent)
    )
    return entity_id, zha_entity


@pytest.mark.parametrize(
    ("event_class", "device_class"),
    [
        pytest.param(FakeEvent, EventDeviceClass.BUTTON, id="button"),
        pytest.param(FakeMotionEvent, EventDeviceClass.MOTION, id="motion"),
        pytest.param(FakeNoDeviceClassEvent, None, id="no_device_class"),
    ],
)
async def test_event_entity(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
    device_class: EventDeviceClass | None,
) -> None:
    """Test ZHA event entity is created with the capabilities of the zha entity."""
    entity_id, _ = await _setup_device(hass, setup_zha, zigpy_device_mock)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class
    assert state.attributes[ATTR_EVENT_TYPES] == ["press_end", "multi_press_end"]
    assert state.attributes[ATTR_EVENT_TYPE] is None


@pytest.mark.freeze_time("2026-09-25 12:00:00+00:00")
async def test_event_triggered(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test events triggered by the zha entity are fired in Home Assistant."""
    entity_id, zha_entity = await _setup_device(hass, setup_zha, zigpy_device_mock)

    zha_entity.trigger(ButtonEventType.MULTI_PRESS_END, {ATTR_MULTI_PRESS_COUNT: 2})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2026-09-25T12:00:00.000+00:00"
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_end"
    assert state.attributes[ATTR_MULTI_PRESS_COUNT] == 2

    zha_entity.trigger(ButtonEventType.PRESS_END)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_EVENT_TYPE] == "press_end"
    assert ATTR_MULTI_PRESS_COUNT not in state.attributes


async def test_event_restored(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test the last event is restored when the entity is set up again."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(ENTITY_ID, "2026-09-25T12:00:00.000+00:00"),
                {
                    "last_event_type": "multi_press_end",
                    "last_event_attributes": {ATTR_MULTI_PRESS_COUNT: 2},
                },
            )
        ],
    )

    entity_id, _ = await _setup_device(hass, setup_zha, zigpy_device_mock)
    assert entity_id == ENTITY_ID

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2026-09-25T12:00:00.000+00:00"
    assert state.attributes[ATTR_EVENT_TYPE] == "multi_press_end"
    assert state.attributes[ATTR_MULTI_PRESS_COUNT] == 2


async def test_event_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test removing the entity stops listening to the zha entity."""
    entity_id, zha_entity = await _setup_device(hass, setup_zha, zigpy_device_mock)
    assert zha_entity._listeners[EntityEventTriggeredEvent.event]

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
    assert not zha_entity._listeners[EntityEventTriggeredEvent.event]

    # Must not write state for the removed entity
    zha_entity.trigger(ButtonEventType.PRESS_END)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None

"""Test ZHA infrared."""

from collections.abc import Callable, Coroutine, Generator
from typing import Any
from unittest.mock import patch

from infrared_protocols.commands.nec import NECCommand
import pytest
from zha.application.platforms import ENTITY_REGISTRY, ClusterMatch
from zha.application.platforms.infrared import (
    BaseInfraredEmitter,
    BaseInfraredReceiver,
    InfraredSignal,
)
from zha.exceptions import ZHAException
from zigpy.const import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE
from zigpy.device import ZigbeeDevice
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components import infrared
from homeassistant.components.infrared import (
    InfraredDeviceClass,
    InfraredReceivedSignal,
)
from homeassistant.components.zha.const import DOMAIN
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


class FakeEmitter(BaseInfraredEmitter):
    """Emitter that records what it was asked to transmit."""

    _unique_id_suffix = "fake_emitter"
    _cluster_match = ClusterMatch(
        client_clusters=frozenset({general.OnOff.cluster_id}),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the fake emitter."""
        super().__init__(*args, **kwargs)
        self.sent: list[InfraredSignal] = []

    async def async_send_command(self, signal: InfraredSignal) -> None:
        """Record the signal instead of transmitting it."""
        self.sent.append(signal)


class FakeFailingEmitter(FakeEmitter):
    """Emitter whose transmissions fail."""

    async def async_send_command(self, signal: InfraredSignal) -> None:
        """Fail to transmit the signal."""
        raise ZHAException("Failed to send IR command")


class FakeReceiver(BaseInfraredReceiver):
    """Receiver that captures signals on demand."""

    _unique_id_suffix = "fake_receiver"
    _cluster_match = ClusterMatch(
        client_clusters=frozenset({general.OnOff.cluster_id}),
    )

    def receive(self, signal: InfraredSignal) -> None:
        """Capture a signal, as a concrete subclass would."""
        self._handle_received_signal(signal)


@pytest.fixture(autouse=True)
def infrared_platform_only() -> Generator[None]:
    """Only set up the infrared and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (Platform.INFRARED, Platform.SENSOR),
    ):
        yield


@pytest.fixture
def speed_up_radio_mgr() -> Generator[None]:
    """Remove radio manager delays, which never elapse with time frozen."""
    with (
        patch("homeassistant.components.zha.radio_manager.CONNECT_DELAY_S", 0),
        patch("zha.application.gateway.SHUT_DOWN_DELAY_S", 0),
    ):
        yield


@pytest.fixture
def emitter_class() -> type[FakeEmitter]:
    """Return the fake emitter entity class to discover."""
    return FakeEmitter


@pytest.fixture(autouse=True)
def register_fake_infrared(emitter_class: type[FakeEmitter]) -> Generator[None]:
    """Make zha discover the fake infrared entities on the OnOff client cluster."""
    with patch.dict(
        ENTITY_REGISTRY,
        {
            general.OnOff.cluster_id: [
                *ENTITY_REGISTRY[general.OnOff.cluster_id],
                emitter_class,
                FakeReceiver,
            ]
        },
    ):
        yield


async def _setup_device(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> ZHADeviceProxy:
    """Join a remote with an OnOff client cluster."""
    await setup_zha()

    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_PROFILE: zha.PROFILE_ID,
                SIG_EP_TYPE: zha.DeviceType.REMOTE_CONTROL,
                SIG_EP_INPUT: [general.Basic.cluster_id],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
            }
        },
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    return gateway_proxy.get_device_proxy(zigpy_device.ieee)


def _get_entity[T: FakeEmitter | FakeReceiver](
    hass: HomeAssistant, zha_device_proxy: ZHADeviceProxy, entity_class: type[T]
) -> tuple[str, T]:
    """Return the HA entity ID and the zha entity of the given class."""
    zha_entity = next(
        entity
        for entity in zha_device_proxy.device.platform_entities.values()
        if isinstance(entity, entity_class)
    )
    entity_id = er.async_get(hass).async_get_entity_id(
        Platform.INFRARED, DOMAIN, zha_entity.unique_id
    )
    assert entity_id is not None

    return entity_id, zha_entity


async def test_infrared_entities(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test ZHA infrared emitters and receivers are created."""
    zha_device_proxy = await _setup_device(hass, setup_zha, zigpy_device_mock)
    emitter_id, _ = _get_entity(hass, zha_device_proxy, FakeEmitter)
    receiver_id, _ = _get_entity(hass, zha_device_proxy, FakeReceiver)

    assert infrared.async_get_emitters(hass) == [emitter_id]
    assert infrared.async_get_receivers(hass) == [receiver_id]

    emitter_state = hass.states.get(emitter_id)
    assert emitter_state
    assert emitter_state.state == STATE_UNKNOWN
    assert emitter_state.attributes[ATTR_DEVICE_CLASS] == InfraredDeviceClass.EMITTER

    receiver_state = hass.states.get(receiver_id)
    assert receiver_state
    assert receiver_state.state == STATE_UNKNOWN
    assert receiver_state.attributes[ATTR_DEVICE_CLASS] == InfraredDeviceClass.RECEIVER


@pytest.mark.freeze_time("2026-09-29 12:00:00+00:00")
async def test_infrared_send_command(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test IR commands are sent through the zha emitter as raw timings."""
    zha_device_proxy = await _setup_device(hass, setup_zha, zigpy_device_mock)
    entity_id, zha_entity = _get_entity(hass, zha_device_proxy, FakeEmitter)

    command = NECCommand(address=0x04, command=0x08, modulation=38000)
    await infrared.async_send_command(hass, entity_id, command)

    assert zha_entity.sent == [
        InfraredSignal(timings=command.get_raw_timings(), modulation=38000)
    ]
    assert hass.states.get(entity_id).state == "2026-09-29T12:00:00.000+00:00"


@pytest.mark.parametrize("emitter_class", [FakeFailingEmitter])
async def test_infrared_send_command_failure(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test ZHA errors are raised as Home Assistant errors."""
    zha_device_proxy = await _setup_device(hass, setup_zha, zigpy_device_mock)
    entity_id, _ = _get_entity(hass, zha_device_proxy, FakeFailingEmitter)

    command = NECCommand(address=0x04, command=0x08, modulation=38000)
    with pytest.raises(HomeAssistantError, match="Failed to send IR command"):
        await infrared.async_send_command(hass, entity_id, command)

    assert hass.states.get(entity_id).state == STATE_UNKNOWN


@pytest.mark.freeze_time("2026-09-29 12:00:00+00:00")
async def test_infrared_received_signal(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test signals captured by the zha receiver are dispatched to subscribers."""
    zha_device_proxy = await _setup_device(hass, setup_zha, zigpy_device_mock)
    entity_id, zha_entity = _get_entity(hass, zha_device_proxy, FakeReceiver)

    received_signals: list[InfraredReceivedSignal] = []
    unsub = infrared.async_subscribe_receiver(hass, entity_id, received_signals.append)

    zha_entity.receive(InfraredSignal(timings=[9000, -4500], modulation=38000))
    zha_entity.receive(InfraredSignal(timings=[560, -1690]))
    await hass.async_block_till_done()

    assert received_signals == [
        InfraredReceivedSignal(timings=[9000, -4500], modulation=38000),
        InfraredReceivedSignal(timings=[560, -1690]),
    ]
    assert hass.states.get(entity_id).state == "2026-09-29T12:00:00.000+00:00"

    unsub()
    zha_entity.receive(InfraredSignal(timings=[9000, -4500]))
    await hass.async_block_till_done()
    assert len(received_signals) == 2


async def test_infrared_receiver_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
) -> None:
    """Test removing the receiver stops listening to the zha entity."""
    zha_device_proxy = await _setup_device(hass, setup_zha, zigpy_device_mock)
    entity_id, zha_entity = _get_entity(hass, zha_device_proxy, FakeReceiver)

    received_signals: list[InfraredReceivedSignal] = []
    infrared.async_subscribe_receiver(hass, entity_id, received_signals.append)

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None

    # Subscribers live on the removed entity, so they only fire if the listener leaked
    zha_entity.receive(InfraredSignal(timings=[9000, -4500]))
    await hass.async_block_till_done()
    assert received_signals == []

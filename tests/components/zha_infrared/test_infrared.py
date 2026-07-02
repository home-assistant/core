"""Tests for ZHA Infrared receiver entity behavior."""

import pytest

from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.zha_infrared import infrared as zha_infrared
from homeassistant.components.zha_infrared.helpers import (
    CodecSpec,
    DeviceMatchRule,
    DeviceProfile,
    ProfileFeatures,
    ReceiveArmCommandSpec,
    ReceiveSpec,
    SupportedDevice,
    TransportSpec,
)


def _build_receiver_entity() -> zha_infrared.ZhaInfraredReceiverEntity:
    """Create a receiver entity with minimal profile data."""
    profile = DeviceProfile(
        profile_id="test",
        name="Test",
        match=DeviceMatchRule(
            models=set(),
            manufacturers=set(),
            device_types=set(),
            required_in_clusters=set(),
        ),
        features=ProfileFeatures(send_ir=False, receive_ir=True),
        transport=TransportSpec(
            cluster_id=0xE004,
            command_id=0x02,
            command_arg="code",
            expect_reply=False,
        ),
        codec=CodecSpec(name="tuya_base64_rawtimings_v1"),
        receive=ReceiveSpec(
            method="cluster_attribute_read",
            attribute="last_learned_ir_code",
            poll_interval_seconds=1,
            arm_command=ReceiveArmCommandSpec(
                call_command_id=1,
                call_arg="on_off",
                call_value=True,
                state_cluster_id=0x0006,
                state_attribute="on_off",
                state_armed_value=False,
                state_disarmed_value=True,
                min_command_interval_seconds=2,
                repeat_interval_seconds=30,
                reset_interval_on_update=True,
                reset_on_arm_value=True,
            ),
        ),
    )
    device = SupportedDevice(
        name="Test Device",
        ieee="00:11:22:33:44:55:66:77",
        endpoint_id=1,
        profile=profile,
    )
    return zha_infrared.ZhaInfraredReceiverEntity(device)


@pytest.mark.asyncio
async def test_receiver_process_payload_deduplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Receiver should dispatch only once for identical payload."""
    entity = _build_receiver_entity()
    received: list[InfraredReceivedSignal] = []
    entity._handle_received_signal = received.append  # type: ignore[method-assign]

    monkeypatch.setattr(zha_infrared, "decode_received_payload", lambda *_: [100, -200])

    await entity.async_process_payload("payload")
    await entity.async_process_payload("payload")

    assert received == [InfraredReceivedSignal(timings=[100, -200])]


@pytest.mark.asyncio
async def test_receiver_process_payload_handles_decode_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Receiver should ignore decode errors without raising."""
    entity = _build_receiver_entity()

    def _raise_decode_error(*_: object) -> list[int]:
        raise ValueError("bad payload")

    monkeypatch.setattr(zha_infrared, "decode_received_payload", _raise_decode_error)

    await entity.async_process_payload("payload")
    assert entity._last_payload is None

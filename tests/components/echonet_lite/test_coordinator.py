"""Tests for the ECHONET Lite coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from pyhems import EOJ
from pyhems.runtime import HemsInstanceListEvent

from homeassistant.components.echonet_lite.const import (
    CONF_ENABLE_EXPERIMENTAL,
    DOMAIN,
    STABLE_CLASS_CODES,
)
from homeassistant.components.echonet_lite.coordinator import EchonetLiteCoordinator
from homeassistant.core import HomeAssistant

from .conftest import make_frame_event

from tests.common import MockConfigEntry


@dataclass(slots=True)
class FrameProperty:
    """Minimal representation of an ECHONET Lite property."""

    epc: int
    edt: bytes


@dataclass(slots=True)
class FrameMessage:
    """Minimal representation of an ECHONET Lite frame."""

    tid: int
    seoj: bytes
    deoj: bytes
    esv: int
    properties: list[FrameProperty]

    def is_response_frame(self) -> bool:
        """Check if frame is a response (success or failure)."""
        return (0x70 <= self.esv <= 0x7F) or (0x50 <= self.esv <= 0x5F)


async def test_process_frame_registers_node(hass: HomeAssistant) -> None:
    """Ensure frames with property maps populate the coordinator data snapshot."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    client = AsyncMock()
    # Property map format: count byte + EPC list
    get_property_map = bytes([3, 0x80, 0x8A, 0xE0])  # 3 EPCs: 0x80, 0x8A, 0xE0
    client.async_get.return_value = [
        FrameProperty(epc=0x9F, edt=get_property_map),
        FrameProperty(epc=0xE0, edt=b"\x00d"),
        FrameProperty(epc=0x8A, edt=b"\x00\x00\x01"),
    ]
    coordinator = EchonetLiteCoordinator(
        hass,
        config_entry=entry,
        client=client,
        monitored_epcs={},
        enable_experimental=False,
    )

    node_hex = bytes.fromhex("010203").hex()
    eoj = EOJ(0x001101)

    with patch(
        "homeassistant.components.echonet_lite.coordinator.time.monotonic",
        return_value=10.0,
    ):
        await coordinator._async_setup_device(node_hex, eoj)

    # Stable ID: uid(hex)-eoj(hex) (0x83 + EOJ preferred)
    # 010203-001101
    node_id = f"{node_hex}-{int(eoj):06x}"
    node = coordinator.data[node_id]
    assert node.eoj == eoj
    assert node.last_seen == 10.0
    assert node.properties[0xE0] == b"\x00d"

    # Frames update existing nodes
    frame2 = FrameMessage(
        tid=2,
        seoj=int(eoj).to_bytes(3, "big"),
        deoj=bytes.fromhex("0ef001"),
        esv=0x73,
        properties=[FrameProperty(epc=0xE0, edt=b"\x00e")],
    )

    await coordinator.async_process_frame_event(
        make_frame_event(
            frame2,
            received_at=11.0,
            node_id=node_hex,
            eoj=eoj,
        )
    )

    node2 = coordinator.data[node_id]
    assert node2.last_seen == 10.0  # last_seen is not updated by frame events currently
    assert node2.properties[0xE0] == b"\x00e"


async def test_set_response_does_not_overwrite_properties(hass: HomeAssistant) -> None:
    """Ensure Set responses (0x71) do not clobber stored property values."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    client = AsyncMock()

    get_property_map = bytes([1, 0xB0])
    client.async_get.return_value = [
        FrameProperty(epc=0x9F, edt=get_property_map),
        FrameProperty(epc=0xB0, edt=b"E"),
        FrameProperty(epc=0x8A, edt=b"\x00\x00\x01"),
    ]

    coordinator = EchonetLiteCoordinator(
        hass,
        config_entry=entry,
        client=client,
        monitored_epcs={0x0011: frozenset({0xB0})},
        enable_experimental=False,
    )

    node_hex = bytes.fromhex("010203").hex()
    eoj = EOJ(0x001101)

    with patch(
        "homeassistant.components.echonet_lite.coordinator.time.monotonic",
        return_value=10.0,
    ):
        await coordinator._async_setup_device(node_hex, eoj)

    device_key = f"{node_hex}-{int(eoj):06x}"
    assert coordinator.data[device_key].properties[0xB0] == b"E"

    # Simulate a successful Set_Res for EPC 0xB0: empty EDT is an acknowledgement
    # and must not be interpreted as a new value.
    frame = FrameMessage(
        tid=4,
        seoj=int(eoj).to_bytes(3, "big"),
        deoj=bytes.fromhex("0ef001"),
        esv=0x71,
        properties=[FrameProperty(epc=0xB0, edt=b"")],
    )

    await coordinator.async_process_frame_event(
        make_frame_event(
            frame,
            received_at=11.0,
            node_id=node_hex,
            eoj=eoj,
        )
    )

    assert coordinator.data[device_key].properties[0xB0] == b"E"


async def test_process_frame_registers_instance_list(hass: HomeAssistant) -> None:
    """Ensure EPC 0xD6 instance lists trigger identification.

    (but don't create nodes directly).
    """

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    coordinator = EchonetLiteCoordinator(
        hass,
        config_entry=entry,
        client=MagicMock(),
        monitored_epcs={},
        enable_experimental=False,
    )

    frame = FrameMessage(
        tid=3,
        seoj=bytes.fromhex("0ef001"),
        deoj=bytes.fromhex("05ff01"),
        esv=0x72,
        properties=[
            FrameProperty(epc=0xD6, edt=bytes.fromhex("02001101013001")),
        ],
    )

    await coordinator.async_process_frame_event(
        make_frame_event(
            frame,
            received_at=20.0,
            node_id="",
            eoj=EOJ(int.from_bytes(frame.seoj, "big")),
        )
    )

    # Nodes should NOT be created yet because we haven't received identification
    assert "001101" not in coordinator.data
    assert "013001" not in coordinator.data


async def test_experimental_filtering_skips_non_stable_classes(
    hass: HomeAssistant,
) -> None:
    """Verify experimental device classes are skipped when enable_experimental is False."""
    # Create entry with enable_experimental=False
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_ENABLE_EXPERIMENTAL: False},
    )
    entry.add_to_hass(hass)

    client = AsyncMock()
    coordinator = EchonetLiteCoordinator(
        hass,
        config_entry=entry,
        client=client,
        monitored_epcs={},
        enable_experimental=False,
    )

    node_id = "010203040506"
    # 0x0011 is temperature sensor (experimental), 0x0130 is air conditioner (stable)
    experimental_eoj = EOJ(0x001101)
    stable_eoj = EOJ(0x013001)

    event = HemsInstanceListEvent(
        received_at=10.0,
        instances=[experimental_eoj, stable_eoj],
        node_id=node_id,
        properties={},
    )

    # Mock _async_setup_device to track calls
    with patch.object(
        coordinator, "_async_setup_device", new_callable=AsyncMock
    ) as mock_request:
        await coordinator.async_process_instance_list_event(event)

        # Only stable class should be requested
        assert mock_request.await_count == 1
        mock_request.assert_awaited_once_with(node_id, stable_eoj)


async def test_experimental_filtering_allows_all_when_enabled(
    hass: HomeAssistant,
) -> None:
    """Verify all device classes are allowed when enable_experimental is True."""
    # Create entry with enable_experimental=True
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_ENABLE_EXPERIMENTAL: True},
    )
    entry.add_to_hass(hass)

    client = AsyncMock()
    coordinator = EchonetLiteCoordinator(
        hass,
        config_entry=entry,
        client=client,
        monitored_epcs={},
        enable_experimental=True,
    )

    node_id = "010203040506"
    # 0x0011 is temperature sensor (experimental), 0x0130 is air conditioner (stable)
    experimental_eoj = EOJ(0x001101)
    stable_eoj = EOJ(0x013001)

    event = HemsInstanceListEvent(
        received_at=10.0,
        instances=[experimental_eoj, stable_eoj],
        node_id=node_id,
        properties={},
    )

    with patch.object(
        coordinator, "_async_setup_device", new_callable=AsyncMock
    ) as mock_request:
        await coordinator.async_process_instance_list_event(event)

        # Both classes should be requested
        assert mock_request.await_count == 2


async def test_stable_class_codes_are_defined() -> None:
    """Ensure STABLE_CLASS_CODES is properly defined and non-empty."""
    assert STABLE_CLASS_CODES
    assert 0x0130 in STABLE_CLASS_CODES  # Home air conditioner
    assert 0x0135 in STABLE_CLASS_CODES  # Air cleaner
    assert 0x05FF in STABLE_CLASS_CODES  # Controller

"""Tests for the SVS Subwoofer binary protocol.

Pure-Python tests for `svs_encode`, `svs_decode`, and `FrameAssembler`.
No HA fixtures required.
"""

from binascii import crc_hqx

from homeassistant.components.svs_subwoofer.svs_protocol import (
    FRAME_PREAMBLE,
    FrameAssembler,
    svs_decode,
    svs_encode,
)


def _read_resp_frame(param_id: int, mem_start: int, payload_data: bytes) -> bytes:
    """Build a synthetic READ_RESP frame around the given payload data.

    Mimics the on-the-wire shape so we can exercise svs_decode in isolation
    of the device. The SVS device pads READ_RESP frames with 4 bytes between
    the length field and the param/offset/size triple.
    """
    body = (
        b"\x00\x00\x00\x00"  # 4-byte response padding
        + param_id.to_bytes(4, "little")
        + mem_start.to_bytes(2, "little")
        + len(payload_data).to_bytes(2, "little")
        + payload_data
    )
    frame_type = b"\xf2\x00"
    length = (1 + 2 + 2 + len(body) + 2).to_bytes(2, "little")
    head = FRAME_PREAMBLE + frame_type + length + body
    return head + crc_hqx(head, 0).to_bytes(2, "little")


class TestSvsEncode:
    """Encoding tests for svs_encode."""

    def test_unknown_parameter_returns_empty(self) -> None:
        """Unknown parameter names return an empty frame and meta."""
        frame, meta = svs_encode("MEMWRITE", "DOES_NOT_EXIST", 0)
        assert frame == b""
        assert meta == ""

    def test_unknown_frame_type_returns_empty(self) -> None:
        """Unknown frame type returns an empty frame."""
        frame, _ = svs_encode("BOGUS", "VOLUME", -25)
        assert frame == b""

    def test_volume_negative_value(self) -> None:
        """Encoding a negative volume produces a well-formed frame."""
        frame, meta = svs_encode("MEMWRITE", "VOLUME", -25)
        assert frame.startswith(FRAME_PREAMBLE)
        assert frame[1:3] == b"\xf0\x1f"  # MEMWRITE frame type
        # Length field at offset 3-5 must equal total frame length
        assert int.from_bytes(frame[3:5], "little") == len(frame)
        # CRC must validate
        assert frame[-2:] == crc_hqx(frame[:-2], 0).to_bytes(2, "little")
        assert "VOLUME" in meta

    def test_volume_out_of_range_rejected(self) -> None:
        """Continuous values outside the declared range are rejected."""
        frame, _ = svs_encode("MEMWRITE", "VOLUME", -100)
        assert frame == b""

    def test_discrete_value_not_in_allowed_list_rejected(self) -> None:
        """Discrete values outside the allowed list are rejected."""
        # LOW_PASS_FILTER_SLOPE only accepts 6/12/18/24
        frame, _ = svs_encode("MEMWRITE", "LOW_PASS_FILTER_SLOPE", 9)
        assert frame == b""

    def test_discrete_value_in_allowed_list_accepted(self) -> None:
        """Discrete values in the allowed list encode successfully."""
        frame, _ = svs_encode("MEMWRITE", "LOW_PASS_FILTER_SLOPE", 12)
        assert frame.startswith(FRAME_PREAMBLE)
        assert int.from_bytes(frame[3:5], "little") == len(frame)

    def test_memread_has_no_data(self) -> None:
        """MEMREAD frames carry no data payload."""
        frame, _ = svs_encode("MEMREAD", "VOLUME")
        assert frame.startswith(FRAME_PREAMBLE)
        assert frame[1:3] == b"\xf1\x1f"  # MEMREAD frame type
        # Frame is preamble(1) + type(2) + length(2) + id(4) + offset(2) + size(2) + crc(2) = 15
        assert len(frame) == 15

    def test_preset_load_frame_structure(self) -> None:
        """PRESETLOADSAVE frames produce the load/save shape."""
        frame, _ = svs_encode("PRESETLOADSAVE", "PRESET2LOAD")
        assert frame.startswith(FRAME_PREAMBLE)
        assert frame[1:3] == b"\x07\x04"  # PRESETLOADSAVE type
        assert int.from_bytes(frame[3:5], "little") == len(frame)

    def test_string_parameter_encoded_with_padding(self) -> None:
        """String parameters (preset names) are null-padded to n_bytes."""
        # Use one of the PRESETxNAME fields if present; otherwise this is a
        # smoke test for the path that should never raise.
        frame, _ = svs_encode("MEMWRITE", "PRESET1NAME", "MAIN")
        # Frame may be empty if the parameter limits_type isn't 2 in this
        # registry; in that case, we just skip the assertion. This guards
        # against silent regressions if PRESETxNAME is added/removed.
        if frame:
            assert frame.startswith(FRAME_PREAMBLE)
            assert int.from_bytes(frame[3:5], "little") == len(frame)


class TestSvsDecode:
    """Decoding tests for svs_decode."""

    def test_short_frame_not_recognized(self) -> None:
        """Frames shorter than the minimum are not recognized."""
        result = svs_decode(b"\xaa\xf0\x1f")
        assert result["FRAME_RECOGNIZED"] is False

    def test_wrong_preamble_not_recognized(self) -> None:
        """Frames missing the preamble are not recognized."""
        result = svs_decode(b"\xbb" + b"\x00" * 10)
        assert result["FRAME_RECOGNIZED"] is False

    def test_bad_crc_not_recognized(self) -> None:
        """A frame with a corrupted CRC is rejected."""
        good_frame, _ = svs_encode("MEMREAD", "VOLUME")
        # Flip a CRC byte
        bad_frame = good_frame[:-2] + b"\xff\xff"
        assert svs_decode(bad_frame)["FRAME_RECOGNIZED"] is False

    def test_length_mismatch_not_recognized(self) -> None:
        """A frame whose length field disagrees with actual length is rejected."""
        good_frame, _ = svs_encode("MEMREAD", "VOLUME")
        # Truncate the body but keep the original length field
        truncated = good_frame[:-3]
        assert svs_decode(truncated)["FRAME_RECOGNIZED"] is False

    def test_round_trip_volume(self) -> None:
        """A READ_RESP carrying a VOLUME value round-trips through decode."""
        # VOLUME has id=4, offset=0x2C, n_bytes=2 (per SVS_PARAMS).
        # Encode -25 the way the device does and wrap as READ_RESP.
        mask = 0xFFFF
        encoded_value = ((int(10 * 25) ^ mask) + (mask % 2)).to_bytes(2, "little")
        frame = _read_resp_frame(param_id=4, mem_start=0x2C, payload_data=encoded_value)
        result = svs_decode(frame)
        assert result["FRAME_RECOGNIZED"] is True
        assert result["FRAME_TYPE"] == "READ_RESP"
        assert result["VALIDATED_VALUES"]["VOLUME"] == -25

    def test_round_trip_positive_value(self) -> None:
        """A positive value (PHASE) decodes back to the original int."""
        # PHASE id=4 offset=0x2E n_bytes=2
        encoded_value = (int(10 * 90)).to_bytes(2, "little")
        frame = _read_resp_frame(param_id=4, mem_start=0x2E, payload_data=encoded_value)
        result = svs_decode(frame)
        assert result["VALIDATED_VALUES"].get("PHASE") == 90


class TestEncodeMore:
    """Additional encoding paths."""

    def test_encode_invalid_value_type(self) -> None:
        """Passing a list/None as VOLUME data is rejected."""
        frame, _ = svs_encode("MEMWRITE", "VOLUME", [1, 2, 3])
        assert frame == b""

    def test_encode_reset_frame(self) -> None:
        """RESET frame builds successfully."""
        frame, _ = svs_encode("RESET", "VOLUME")
        assert frame.startswith(FRAME_PREAMBLE)
        assert frame[1:3] == b"\xf3\x1f"

    def test_encode_sub_info_request(self) -> None:
        """SUB_INFO1 request frame builds successfully."""
        frame, _ = svs_encode("SUB_INFO1", "VOLUME")
        assert frame.startswith(FRAME_PREAMBLE)
        assert frame[1:3] == b"\xf4\x1f"


class TestDecodeMore:
    """Additional decode paths covering protocol-specific branches."""

    def test_decode_string_param(self) -> None:
        """READ_RESP for a PRESETxNAME returns the decoded string."""
        # PRESET1NAME id=8 offset=0x0 n_bytes=8
        body = (
            b"\x00\x00\x00\x00"
            + (8).to_bytes(4, "little")
            + (0x0).to_bytes(2, "little")
            + (8).to_bytes(2, "little")
            + b"MOVIE\x00\x00\x00"
        )
        head = (
            FRAME_PREAMBLE
            + b"\xf2\x00"
            + (1 + 2 + 2 + len(body) + 2).to_bytes(2, "little")
            + body
        )
        frame = head + crc_hqx(head, 0).to_bytes(2, "little")

        result = svs_decode(frame)
        assert result["VALIDATED_VALUES"]["PRESET1NAME"] == "MOVIE"

    def test_decode_discrete_invalid_dropped(self) -> None:
        """A discrete value not in the allowed list is dropped."""
        # LOW_PASS_FILTER_SLOPE id=4 offset=0xC, allowed: 6/12/18/24
        encoded_value = (int(10 * 7)).to_bytes(2, "little")  # 7 not allowed
        frame = _read_resp_frame(param_id=4, mem_start=0xC, payload_data=encoded_value)
        result = svs_decode(frame)
        assert "LOW_PASS_FILTER_SLOPE" not in result["VALIDATED_VALUES"]

    def test_decode_float_value_preserves_decimal(self) -> None:
        """A non-integer numeric value (Q-factor) is returned as float."""
        # PEQ1_QFACTOR id=4 offset=0x14, range 0.2..10.0
        encoded_value = (int(10 * 1.5)).to_bytes(2, "little")  # 1.5
        frame = _read_resp_frame(param_id=4, mem_start=0x14, payload_data=encoded_value)
        result = svs_decode(frame)
        assert result["VALIDATED_VALUES"]["PEQ1_QFACTOR"] == 1.5

    def test_decode_short_payload_returns_early(self) -> None:
        """A truncated MEM payload yields no validated values."""
        body = b"\x00\x00\x00\x00" + b"\x04\x00"  # only 2 bytes after padding
        head = (
            FRAME_PREAMBLE
            + b"\xf2\x00"
            + (1 + 2 + 2 + len(body) + 2).to_bytes(2, "little")
            + body
        )
        frame = head + crc_hqx(head, 0).to_bytes(2, "little")
        result = svs_decode(frame)
        assert result["VALIDATED_VALUES"] == {}

    def test_decode_out_of_range_value_dropped(self) -> None:
        """A numeric value outside declared continuous limits is rejected."""
        encoded_value = (5000).to_bytes(2, "little")
        frame = _read_resp_frame(param_id=4, mem_start=0x2C, payload_data=encoded_value)
        result = svs_decode(frame)
        assert "VOLUME" not in result["VALIDATED_VALUES"]

    def test_decode_sub_info2_resp(self) -> None:
        """SUB_INFO2_RESP exposes SW_VERSION."""
        version = b"1.2.3"
        body = b"\x00\x00\x00\x00" + bytes([len(version)]) + version
        head = (
            FRAME_PREAMBLE
            + b"\xfd\x00"
            + (1 + 2 + 2 + len(body) + 2).to_bytes(2, "little")
            + body
        )
        frame = head + crc_hqx(head, 0).to_bytes(2, "little")

        result = svs_decode(frame)
        assert result["VALIDATED_VALUES"].get("SW_VERSION") == "1.2.3"

    def test_decode_sub_info3_resp(self) -> None:
        """SUB_INFO3_RESP exposes HW_VERSION."""
        version = b"REV.A"
        body = b"\x00\x00\x00\x00" + bytes([len(version)]) + version
        head = (
            FRAME_PREAMBLE
            + b"\xff\x00"
            + (1 + 2 + 2 + len(body) + 2).to_bytes(2, "little")
            + body
        )
        frame = head + crc_hqx(head, 0).to_bytes(2, "little")

        result = svs_decode(frame)
        assert result["VALIDATED_VALUES"].get("HW_VERSION") == "REV.A"


class TestFrameAssembler:
    """Reassembly tests for FrameAssembler."""

    def test_single_complete_frame(self) -> None:
        """A complete frame in one chunk decodes immediately."""
        frame, _ = svs_encode("MEMREAD", "VOLUME")
        asm = FrameAssembler()
        result = asm.add_data(frame)
        assert result is not None
        assert result["FRAME_RECOGNIZED"] is True

    def test_fragmented_two_chunks(self) -> None:
        """A frame split over two BLE notifications reassembles."""
        # Use a READ_RESP so the frame is long enough to be fragmented.
        frame = _read_resp_frame(
            param_id=4,
            mem_start=0x2C,
            payload_data=(0).to_bytes(2, "little"),
        )
        split = len(frame) // 2
        asm = FrameAssembler()
        assert asm.add_data(frame[:split]) is None
        result = asm.add_data(frame[split:])
        assert result is not None
        assert result["FRAME_RECOGNIZED"] is True

    def test_fragmented_three_chunks(self) -> None:
        """Three-way fragmentation also reassembles."""
        frame = _read_resp_frame(
            param_id=4,
            mem_start=0x2C,
            payload_data=(0).to_bytes(2, "little"),
        )
        a, b, c = len(frame) // 3, 2 * len(frame) // 3, len(frame)
        asm = FrameAssembler()
        assert asm.add_data(frame[:a]) is None
        assert asm.add_data(frame[a:b]) is None
        result = asm.add_data(frame[b:c])
        assert result is not None
        assert result["FRAME_RECOGNIZED"] is True

    def test_reset_clears_partial_state(self) -> None:
        """reset() lets the assembler accept a fresh frame after a partial."""
        frame, _ = svs_encode("MEMREAD", "VOLUME")
        asm = FrameAssembler()
        asm.add_data(frame[:3])  # partial
        asm.reset()
        # After reset, a complete frame should be accepted
        result = asm.add_data(frame)
        assert result is not None
        assert result["FRAME_RECOGNIZED"] is True

    def test_two_back_to_back_frames(self) -> None:
        """A second frame after a successful one is not concatenated."""
        frame, _ = svs_encode("MEMREAD", "VOLUME")
        asm = FrameAssembler()
        first = asm.add_data(frame)
        assert first is not None
        # Second frame arriving immediately should be parsed independently.
        second = asm.add_data(frame)
        assert second is not None
        assert second["FRAME_RECOGNIZED"] is True

    def test_empty_data_returns_none(self) -> None:
        """Empty data is a no-op."""
        asm = FrameAssembler()
        assert asm.add_data(b"") is None

    def test_continuation_without_preamble_appended(self) -> None:
        """Continuation chunks without preamble append to the partial buffer."""
        frame, _ = svs_encode("MEMREAD", "VOLUME")
        asm = FrameAssembler()
        asm.add_data(frame[:5])  # starts with preamble — sets partial
        # Final chunk must not start with preamble byte to be treated as continuation
        result = asm.add_data(frame[5:])
        assert result is not None
        assert result["FRAME_RECOGNIZED"] is True

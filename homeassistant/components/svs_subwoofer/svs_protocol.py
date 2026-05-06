"""SVS Subwoofer BLE Protocol Implementation.

Extracted and refactored from pySVS.py by Logon84.
https://github.com/logon84/pySVS
"""

from binascii import crc_hqx, hexlify
from dataclasses import dataclass
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Frame constants
FRAME_PREAMBLE = b"\xaa"

# Threshold for detecting negative values in the SVS protocol encoding.
# Values >= this threshold are treated as negative (two's complement style with XOR mask).
NEGATIVE_VALUE_THRESHOLD = 0xF000

# Frame type lookup for encoding/decoding
SVS_FRAME_TYPES: dict[str, bytes] = {
    "PRESETLOADSAVE": b"\x07\x04",
    "MEMWRITE": b"\xf0\x1f",
    "MEMREAD": b"\xf1\x1f",
    "READ_RESP": b"\xf2\x00",
    "RESET": b"\xf3\x1f",
    "SUB_INFO1": b"\xf4\x1f",
    "SUB_INFO1_RESP": b"\xf5\x00",
    "SUB_INFO2": b"\xfc\x1f",
    "SUB_INFO2_RESP": b"\xfd\x00",
    "SUB_INFO3": b"\xfe\x1f",
    "SUB_INFO3_RESP": b"\xff\x00",
}


@dataclass
class SVSParameter:
    """Parameter definition for SVS subwoofer."""

    id: int
    offset: int
    limits: list[Any]
    limits_type: int | str  # 0=continuous, 1=discrete, 2=string, "group"
    n_bytes: int
    reset_id: int


# Complete parameter registry from pySVS.py
SVS_PARAMS: dict[str, SVSParameter] = {
    "FULL_SETTINGS": SVSParameter(
        id=4, offset=0x0, limits=[None], limits_type="group", n_bytes=52, reset_id=-1
    ),
    "DISPLAY": SVSParameter(
        id=4, offset=0x0, limits=[0, 1, 2], limits_type=1, n_bytes=2, reset_id=0
    ),
    "DISPLAY_TIMEOUT": SVSParameter(
        id=4,
        offset=0x2,
        limits=[0, 10, 20, 30, 40, 50, 60],
        limits_type=1,
        n_bytes=2,
        reset_id=1,
    ),
    "STANDBY": SVSParameter(
        id=4, offset=0x4, limits=[0, 1, 2], limits_type=1, n_bytes=2, reset_id=2
    ),
    "BRIGHTNESS": SVSParameter(
        id=4,
        offset=0x6,
        limits=[0, 1, 2, 3, 4, 5, 6, 7],
        limits_type=1,
        n_bytes=2,
        reset_id=14,
    ),
    "LOW_PASS_FILTER_ALL_SETTINGS": SVSParameter(
        id=4, offset=0x8, limits=[None], limits_type="group", n_bytes=6, reset_id=3
    ),
    "LOW_PASS_FILTER_ENABLE": SVSParameter(
        id=4, offset=0x8, limits=[0, 1], limits_type=1, n_bytes=2, reset_id=3
    ),
    "LOW_PASS_FILTER_FREQ": SVSParameter(
        id=4, offset=0xA, limits=[30, 200], limits_type=0, n_bytes=2, reset_id=3
    ),
    "LOW_PASS_FILTER_SLOPE": SVSParameter(
        id=4, offset=0xC, limits=[6, 12, 18, 24], limits_type=1, n_bytes=2, reset_id=3
    ),
    "PEQ1_ALL_SETTINGS": SVSParameter(
        id=4, offset=0xE, limits=[None], limits_type="group", n_bytes=8, reset_id=5
    ),
    "PEQ1_ENABLE": SVSParameter(
        id=4, offset=0xE, limits=[0, 1], limits_type=1, n_bytes=2, reset_id=5
    ),
    "PEQ1_FREQ": SVSParameter(
        id=4, offset=0x10, limits=[20, 200], limits_type=0, n_bytes=2, reset_id=5
    ),
    "PEQ1_BOOST": SVSParameter(
        id=4, offset=0x12, limits=[-12.0, 6.0], limits_type=0, n_bytes=2, reset_id=5
    ),
    "PEQ1_QFACTOR": SVSParameter(
        id=4, offset=0x14, limits=[0.2, 10.0], limits_type=0, n_bytes=2, reset_id=5
    ),
    "PEQ2_ALL_SETTINGS": SVSParameter(
        id=4, offset=0x16, limits=[None], limits_type="group", n_bytes=8, reset_id=5
    ),
    "PEQ2_ENABLE": SVSParameter(
        id=4, offset=0x16, limits=[0, 1], limits_type=1, n_bytes=2, reset_id=5
    ),
    "PEQ2_FREQ": SVSParameter(
        id=4, offset=0x18, limits=[20, 200], limits_type=0, n_bytes=2, reset_id=5
    ),
    "PEQ2_BOOST": SVSParameter(
        id=4, offset=0x1A, limits=[-12.0, 6.0], limits_type=0, n_bytes=2, reset_id=5
    ),
    "PEQ2_QFACTOR": SVSParameter(
        id=4, offset=0x1C, limits=[0.2, 10.0], limits_type=0, n_bytes=2, reset_id=5
    ),
    "PEQ3_ALL_SETTINGS": SVSParameter(
        id=4, offset=0x1E, limits=[None], limits_type="group", n_bytes=8, reset_id=5
    ),
    "PEQ3_ENABLE": SVSParameter(
        id=4, offset=0x1E, limits=[0, 1], limits_type=1, n_bytes=2, reset_id=5
    ),
    "PEQ3_FREQ": SVSParameter(
        id=4, offset=0x20, limits=[20, 200], limits_type=0, n_bytes=2, reset_id=5
    ),
    "PEQ3_BOOST": SVSParameter(
        id=4, offset=0x22, limits=[-12.0, 6.0], limits_type=0, n_bytes=2, reset_id=5
    ),
    "PEQ3_QFACTOR": SVSParameter(
        id=4, offset=0x24, limits=[0.2, 10.0], limits_type=0, n_bytes=2, reset_id=5
    ),
    "ROOM_GAIN_ALL_SETTINGS": SVSParameter(
        id=4, offset=0x26, limits=[None], limits_type="group", n_bytes=6, reset_id=8
    ),
    "ROOM_GAIN_ENABLE": SVSParameter(
        id=4, offset=0x26, limits=[0, 1], limits_type=1, n_bytes=2, reset_id=8
    ),
    "ROOM_GAIN_FREQ": SVSParameter(
        id=4, offset=0x28, limits=[25, 31, 40], limits_type=1, n_bytes=2, reset_id=8
    ),
    "ROOM_GAIN_SLOPE": SVSParameter(
        id=4, offset=0x2A, limits=[6, 12], limits_type=1, n_bytes=2, reset_id=8
    ),
    "VOLUME": SVSParameter(
        id=4, offset=0x2C, limits=[-60, 0], limits_type=0, n_bytes=2, reset_id=12
    ),
    "PHASE": SVSParameter(
        id=4, offset=0x2E, limits=[0, 180], limits_type=0, n_bytes=2, reset_id=9
    ),
    "POLARITY": SVSParameter(
        id=4, offset=0x30, limits=[0, 1], limits_type=1, n_bytes=2, reset_id=10
    ),
    "PORTTUNING": SVSParameter(
        id=4, offset=0x32, limits=[20, 30], limits_type=1, n_bytes=2, reset_id=11
    ),
    "PRESET1NAME": SVSParameter(
        id=8, offset=0x0, limits=[""], limits_type=2, n_bytes=8, reset_id=13
    ),
    "PRESET2NAME": SVSParameter(
        id=9, offset=0x0, limits=[""], limits_type=2, n_bytes=8, reset_id=13
    ),
    "PRESET3NAME": SVSParameter(
        id=0xA, offset=0x0, limits=[""], limits_type=2, n_bytes=8, reset_id=13
    ),
    "PRESET1LOAD": SVSParameter(
        id=0x18, offset=0x1, limits=[None], limits_type=-1, n_bytes=0, reset_id=-1
    ),
    "PRESET2LOAD": SVSParameter(
        id=0x19, offset=0x1, limits=[None], limits_type=-1, n_bytes=0, reset_id=-1
    ),
    "PRESET3LOAD": SVSParameter(
        id=0x1A, offset=0x1, limits=[None], limits_type=-1, n_bytes=0, reset_id=-1
    ),
    "PRESET4LOAD": SVSParameter(
        id=0x1B, offset=0x1, limits=[None], limits_type=-1, n_bytes=0, reset_id=-1
    ),
    "PRESET1SAVE": SVSParameter(
        id=0x1C, offset=0x1, limits=[None], limits_type=-1, n_bytes=0, reset_id=-1
    ),
    "PRESET2SAVE": SVSParameter(
        id=0x1D, offset=0x1, limits=[None], limits_type=-1, n_bytes=0, reset_id=-1
    ),
    "PRESET3SAVE": SVSParameter(
        id=0x1E, offset=0x1, limits=[None], limits_type=-1, n_bytes=0, reset_id=-1
    ),
}


def bytes_to_hex_str(bytes_input: bytes) -> str:  # pragma: no cover - debug helper
    """Convert bytes to hex string."""
    return hexlify(bytes_input).decode("utf-8")


def svs_encode(ftype: str, param: str, data: Any = "") -> tuple[bytes, str]:
    """Encode a command frame for the SVS subwoofer.

    Returns tuple of (frame_bytes, metadata_string).
    """
    param_info = SVS_PARAMS.get(param)
    if param_info is None:
        _LOGGER.error("Unknown parameter: %s", param)
        return (b"", "")

    frame = b""

    if ftype == "PRESETLOADSAVE" and param_info.id >= 0x18:
        # Preset load/save frame
        frame = (
            param_info.id.to_bytes(4, "little")
            + param_info.offset.to_bytes(2, "little")
            + param_info.n_bytes.to_bytes(2, "little")
        )

    elif (
        ftype == "MEMWRITE"
        and param_info.id <= 0xA
        and param_info.limits_type != "group"
    ):
        # Memory write frame with data
        if isinstance(data, str) and len(data) > 0 and param_info.limits_type == 2:
            # String data (preset names)
            encoded_data = bytes(data.ljust(param_info.n_bytes, "\x00"), "utf-8")[
                : param_info.n_bytes
            ]
        elif isinstance(data, (int, float)):
            # Numeric data
            if param_info.limits_type == 1:
                # Discrete values - check if in allowed list
                if data not in param_info.limits:
                    _LOGGER.error("Value %s not in allowed values for %s", data, param)
                    return (b"", "")
            elif param_info.limits_type == 0:
                # Continuous values - check range
                if not (min(param_info.limits) <= data <= max(param_info.limits)):
                    _LOGGER.error("Value %s out of range for %s", data, param)
                    return (b"", "")

            # Encode numeric value (handles negative numbers)
            mask = 0 if data >= 0 else 0xFFFF
            encoded_data = ((int(10 * abs(data)) ^ mask) + (mask % 2)).to_bytes(
                2, "little"
            )
        else:
            _LOGGER.error("Invalid value type for %s: %s", param, type(data))
            return (b"", "")

        frame = (
            param_info.id.to_bytes(4, "little")
            + param_info.offset.to_bytes(2, "little")
            + param_info.n_bytes.to_bytes(2, "little")
            + encoded_data
        )

    elif ftype == "MEMREAD" and param_info.id <= 0xA:
        # Memory read frame
        frame = (
            param_info.id.to_bytes(4, "little")
            + param_info.offset.to_bytes(2, "little")
            + param_info.n_bytes.to_bytes(2, "little")
        )

    elif ftype == "RESET" and param_info.id <= 0xA:
        # Reset frame
        frame = param_info.reset_id.to_bytes(1, "little")

    elif ftype in ["SUB_INFO1", "SUB_INFO2", "SUB_INFO3"]:
        # Subwoofer info request
        frame = b"\x00"

    else:
        _LOGGER.error("Unknown frame type: %s", ftype)
        return (b"", "")

    # Build complete frame with preamble, type, length, and CRC
    frame_type_bytes = SVS_FRAME_TYPES.get(ftype, b"")
    frame = (
        FRAME_PREAMBLE
        + frame_type_bytes
        + (len(frame) + 7).to_bytes(2, "little")
        + frame
    )
    frame = frame + crc_hqx(frame, 0).to_bytes(2, "little")

    # Build metadata string for logging
    meta = f"{ftype} [{param}] {data}" if data != "" else f"{ftype} [{param}]"

    return (frame, meta)


def _decode_numeric_value(raw_bytes: bytes, param_info: SVSParameter) -> Any:
    """Decode a numeric parameter value from raw bytes.

    Returns the decoded value if it falls within the parameter's declared
    limits, or ``None`` if validation fails.
    """
    raw_int = int.from_bytes(raw_bytes, "little")
    mask = 0 if raw_int < NEGATIVE_VALUE_THRESHOLD else 0xFFFF
    value: float = ((-1) ** (mask % 2)) * ((raw_int - (mask % 2)) ^ mask) / 10

    if param_info.limits_type == 1:
        if value not in param_info.limits:
            return None
    elif param_info.limits_type == 0:
        if not (min(param_info.limits) <= value <= max(param_info.limits)):
            return None

    if value == int(value):
        return int(value)
    return value


def _decode_memory_payload(
    payload: bytes, frame_type: str, result: dict[str, Any]
) -> None:
    """Decode the parameter/value pairs out of a MEMWRITE/MEMREAD/READ_RESP body."""
    if len(payload) < 8:
        return

    param_id = int.from_bytes(payload[:4], "little")
    mem_start = int.from_bytes(payload[4:6], "little")
    mem_size = int.from_bytes(payload[6:8], "little")
    data_payload = payload[8:]

    for offset in range(0, mem_size or 2, 2):
        for param_name, param_info in SVS_PARAMS.items():
            if param_info.limits_type == "group":
                continue
            if param_info.id != param_id:
                continue
            if (mem_start + offset) != param_info.offset:
                continue

            result["ATTRIBUTES"].append(param_name)

            if (
                frame_type not in ("READ_RESP", "MEMWRITE")
                or len(data_payload) < param_info.n_bytes
            ):
                break

            raw_bytes = data_payload[: param_info.n_bytes]
            value: Any
            if param_info.limits_type == 2:
                value = raw_bytes.decode("utf-8").rstrip("\x00")
            else:
                value = _decode_numeric_value(raw_bytes, param_info)
                if value is None:
                    break

            result["VALIDATED_VALUES"][param_name] = value
            data_payload = data_payload[param_info.n_bytes :]
            break


def svs_decode(frame: bytes) -> dict[str, Any]:
    """Decode a response frame from the SVS subwoofer.

    Returns dictionary with decoded values and frame metadata.
    """
    result: dict[str, Any] = {
        "FRAME_RECOGNIZED": False,
        "ATTRIBUTES": [],
        "VALIDATED_VALUES": {},
    }

    if len(frame) < 7:
        return result
    if frame[0] != int.from_bytes(FRAME_PREAMBLE, "little"):
        return result
    if int.from_bytes(frame[3:5], "little") != len(frame):
        return result
    if frame[-2:] != crc_hqx(frame[:-2], 0).to_bytes(2, "little"):
        _LOGGER.debug("CRC mismatch in frame")
        return result

    result["FRAME_RECOGNIZED"] = True

    frame_type = "UNKNOWN"
    for key, value in SVS_FRAME_TYPES.items():
        if value == frame[1:3]:
            frame_type = key
            break
    result["FRAME_TYPE"] = frame_type

    payload = frame[5:-2]
    if "RESP" in frame_type and len(payload) >= 4:
        payload = payload[4:]

    if frame_type in ("MEMWRITE", "MEMREAD", "READ_RESP", "PRESETLOADSAVE"):
        _decode_memory_payload(payload, frame_type, result)
    elif frame_type == "SUB_INFO2_RESP" and len(payload) > 1:
        sw_ver_len = payload[0]
        if len(payload) >= 1 + sw_ver_len:
            result["VALIDATED_VALUES"]["SW_VERSION"] = payload[
                1 : 1 + sw_ver_len
            ].decode("utf-8")
            result["ATTRIBUTES"].append("INFO2")

    elif frame_type == "SUB_INFO3_RESP" and len(payload) > 1:
        hw_ver_len = payload[0]
        if len(payload) >= 1 + hw_ver_len:
            result["VALIDATED_VALUES"]["HW_VERSION"] = payload[
                1 : 1 + hw_ver_len
            ].decode("utf-8")
            result["ATTRIBUTES"].append("INFO3")

    return result


class FrameAssembler:
    """Assembles fragmented BLE frames.

    BLE packets can be fragmented across multiple notifications.
    This class accumulates data until a complete frame is received.
    """

    def __init__(self) -> None:
        """Initialize frame assembler."""
        self._partial_frame: bytes = b""
        self._sync: bool = True

    def add_data(self, data: bytes) -> dict[str, Any] | None:
        """Add received data and return decoded frame if complete.

        Args:
            data: Received BLE notification data.

        Returns:
            Decoded frame dictionary if complete, None otherwise.
        """
        if not data:
            return None

        # Check if this is a new frame start
        if data[0] == int.from_bytes(FRAME_PREAMBLE, "little"):
            if not self._sync:  # pragma: no cover - debug log only
                _LOGGER.debug(
                    "Frame fragment out of sync: %s",
                    bytes_to_hex_str(self._partial_frame),
                )
            self._partial_frame = bytes(data)
        else:
            # Continuation of existing frame
            self._partial_frame = self._partial_frame + bytes(data)

        # Try to decode
        decoded = svs_decode(self._partial_frame)
        self._sync = decoded["FRAME_RECOGNIZED"]

        if self._sync:
            _LOGGER.debug(
                "Received frame: %s %s",
                decoded.get("FRAME_TYPE", "UNKNOWN"),
                decoded.get("ATTRIBUTES", []),
            )
            # Clear so a stray continuation doesn't concatenate onto a decoded frame
            self._partial_frame = b""
            return decoded

        return None

    def reset(self) -> None:
        """Reset the frame assembler state."""
        self._partial_frame = b""
        self._sync = True

"""Utilities to help convert mp4s to fmp4s."""
from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from io import BytesIO


def find_box(
    mp4_bytes: bytes, target_type: bytes, box_start: int = 0
) -> Generator[int, None, None]:
    """Find location of first box (or sub_box if box_start provided) of given type."""
    if box_start == 0:
        index = 0
        box_end = len(mp4_bytes)
    else:
        box_end = box_start + int.from_bytes(
            mp4_bytes[box_start : box_start + 4], byteorder="big"
        )
        index = box_start + 8
    while 1:
        if index > box_end - 8:  # End of box, not found
            break
        box_header = mp4_bytes[index : index + 8]
        if box_header[4:8] == target_type:
            yield index
        index += int.from_bytes(box_header[0:4], byteorder="big")


def get_codec_string(mp4_bytes: bytes) -> str:
    """Get RFC 6381 codec string."""
    codecs = []

    # Find moov
    moov_location = next(find_box(mp4_bytes, b"moov"))

    # Find tracks
    for trak_location in find_box(mp4_bytes, b"trak", moov_location):
        # Drill down to media info
        mdia_location = next(find_box(mp4_bytes, b"mdia", trak_location))
        minf_location = next(find_box(mp4_bytes, b"minf", mdia_location))
        stbl_location = next(find_box(mp4_bytes, b"stbl", minf_location))
        stsd_location = next(find_box(mp4_bytes, b"stsd", stbl_location))

        # Get stsd box
        stsd_length = int.from_bytes(
            mp4_bytes[stsd_location : stsd_location + 4], byteorder="big"
        )
        stsd_box = mp4_bytes[stsd_location : stsd_location + stsd_length]

        # Base Codec
        codec = stsd_box[20:24].decode("utf-8")

        # Handle H264
        if (
            codec in ("avc1", "avc2", "avc3", "avc4")
            and stsd_length > 110
            and stsd_box[106:110] == b"avcC"
        ):
            profile = stsd_box[111:112].hex()
            compatibility = stsd_box[112:113].hex()
            # Cap level at 4.1 for compatibility with some Google Cast devices
            level = hex(min(stsd_box[113], 41))[2:]
            codec += "." + profile + compatibility + level

        # Handle H265
        elif (
            codec in ("hev1", "hvc1")
            and stsd_length > 110
            and stsd_box[106:110] == b"hvcC"
        ):
            tmp_byte = int.from_bytes(stsd_box[111:112], byteorder="big")

            # Profile Space
            codec += "."
            profile_space_map = {0: "", 1: "A", 2: "B", 3: "C"}
            profile_space = tmp_byte >> 6
            codec += profile_space_map[profile_space]
            general_profile_idc = tmp_byte & 31
            codec += str(general_profile_idc)

            # Compatibility
            codec += "."
            general_profile_compatibility = int.from_bytes(
                stsd_box[112:116], byteorder="big"
            )
            reverse = 0
            for i in range(0, 32):
                reverse |= general_profile_compatibility & 1
                if i == 31:
                    break
                reverse <<= 1
                general_profile_compatibility >>= 1
            codec += hex(reverse)[2:]

            # Tier Flag
            if (tmp_byte & 32) >> 5 == 0:
                codec += ".L"
            else:
                codec += ".H"
            codec += str(int.from_bytes(stsd_box[122:123], byteorder="big"))

            # Constraint String
            has_byte = False
            constraint_string = ""
            for i in range(121, 115, -1):
                gci = int.from_bytes(stsd_box[i : i + 1], byteorder="big")
                if gci or has_byte:
                    constraint_string = "." + hex(gci)[2:] + constraint_string
                    has_byte = True
            codec += constraint_string

        # Handle Audio
        elif codec == "mp4a":
            oti = None
            dsi = None

            # Parse ES Descriptors
            oti_loc = stsd_box.find(b"\x04\x80\x80\x80")
            if oti_loc > 0:
                oti = stsd_box[oti_loc + 5 : oti_loc + 6].hex()
                codec += f".{oti}"

            dsi_loc = stsd_box.find(b"\x05\x80\x80\x80")
            if dsi_loc > 0:
                dsi_length = int.from_bytes(
                    stsd_box[dsi_loc + 4 : dsi_loc + 5], byteorder="big"
                )
                dsi_data = stsd_box[dsi_loc + 5 : dsi_loc + 5 + dsi_length]
                dsi0 = int.from_bytes(dsi_data[0:1], byteorder="big")
                dsi = (dsi0 & 248) >> 3
                if dsi == 31 and len(dsi_data) >= 2:
                    dsi1 = int.from_bytes(dsi_data[1:2], byteorder="big")
                    dsi = 32 + ((dsi0 & 7) << 3) + ((dsi1 & 224) >> 5)
                codec += f".{dsi}"

        codecs.append(codec)

    return ",".join(codecs)


def read_init(bytes_io: BytesIO) -> bytes:
    """Read the init from a mp4 file."""
    bytes_io.seek(24)
    moov_len = int.from_bytes(bytes_io.read(4), byteorder="big")
    bytes_io.seek(0)
    return bytes_io.read(24 + moov_len)

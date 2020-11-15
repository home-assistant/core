"""Utilities to help convert mp4s to fmp4s."""
import io


def find_box(segment: io.BytesIO, target_type: bytes, box_start: int = 0) -> int:
    """Find location of first box (or sub_box if box_start provided) of given type."""
    if box_start == 0:
        box_end = segment.seek(0, io.SEEK_END)
        segment.seek(0)
        index = 0
    else:
        segment.seek(box_start)
        box_end = box_start + int.from_bytes(segment.read(4), byteorder="big")
        index = box_start + 8
    while 1:
        if index > box_end - 8:  # End of box, not found
            break
        segment.seek(index)
        box_header = segment.read(8)
        if box_header[4:8] == target_type:
            yield index
            segment.seek(index)
        index += int.from_bytes(box_header[0:4], byteorder="big")


def get_init(segment: io.BytesIO) -> bytes:
    """Get init section from fragmented mp4."""
    moof_location = next(find_box(segment, b"moof"))
    segment.seek(0)
    return segment.read(moof_location)


def get_m4s(segment: io.BytesIO, sequence: int) -> bytes:
    """Get m4s section from fragmented mp4."""
    moof_location = next(find_box(segment, b"moof"))
    mfra_location = next(find_box(segment, b"mfra"))
    segment.seek(moof_location)
    return segment.read(mfra_location - moof_location)


def get_codec_string(segment: io.BytesIO) -> str:
    """Get RFC 6381 codec string."""
    codecs = []

    # Find moov
    moov_location = next(find_box(segment, b"moov"))

    # Find tracks
    for trak_location in find_box(segment, b"trak", moov_location):
        # Drill down to media info
        mdia_location = next(find_box(segment, b"mdia", trak_location))
        minf_location = next(find_box(segment, b"minf", mdia_location))
        stbl_location = next(find_box(segment, b"stbl", minf_location))
        stsd_location = next(find_box(segment, b"stsd", stbl_location))

        # Get stsd box
        segment.seek(stsd_location)
        stsd_length = int.from_bytes(segment.read(4), byteorder="big")
        segment.seek(stsd_location)
        stsd_box = segment.read(stsd_length)

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

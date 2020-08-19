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

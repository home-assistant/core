"""Helper functions for the Envisalink integration."""


def find_yaml_info(entry_number: int, info) -> map | None:
    """Locate the given entry from a dict whose keys may be strings."""
    if info is None:
        return None

    for key, entry in info.items():
        if int(key) == entry_number:
            return entry
    return None


def parse_range_string(sequence: str, min_val: int, max_val: int) -> list | None:
    """Parse a string into a set of zones/partitions."""

    # Empty strings are not valid
    if sequence is None or len(sequence) == 0:
        return None

    # Make sure there are only valid characters
    valid_chars = "1234567890,- "
    stripped = sequence.strip(valid_chars)
    if len(stripped) != 0:
        return None

    # Strip whitespace
    sequence = sequence.strip(" ")

    range_list = []
    for seg in sequence.split(","):
        nums = seg.split("-")
        for num_str in nums:
            if len(num_str) == 0:
                return None
            value = int(num_str)
            if value < min_val or value > max_val:
                return None
        if len(nums) == 1:
            range_list.append(int(nums[0]))
        elif len(nums) == 2:
            for i in range(int(nums[0]), int(nums[1]) + 1):
                range_list.append(i)
        else:
            return None

    if len(range_list) == 0:
        return None

    return sorted(set(range_list))


def generate_range_string(seq: set) -> str | None:
    """Generate a string representation of a range of zones/partitions."""
    if len(seq) == 0:
        return None
    lst = list(seq)
    if len(seq) == 1:
        return str(lst[0])

    result = ""
    lst.sort()
    end = start = lst[0]
    for i in lst[1:]:
        if i == (end + 1):
            end = i
        else:
            if start == end:
                result += f"{start},"
            else:
                result += f"{start}-{end},"
            start = end = i

    if start == end:
        result += f"{start}"
    else:
        result += f"{start}-{end}"
    return result

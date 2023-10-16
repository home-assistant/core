def percent_encode(str):  # noqa: D100, D103
    if str is None:
        return ""

    result_str = ""
    for char in str.encode():
        if (
            char >= 33
            and char <= 0x7E
            and char != 34
            and char != 37
            and char != 39
            and char != 44
            and char != 92
        ):
            result_str += chr(char)
        else:
            result_str += "%"
            result_str += format(char, "x").upper()
    return result_str


def sum_char_codes(str):  # noqa: D103
    sum = 0
    for char in str.encode():
        if char < 0x80:
            sum += char
    return sum


def feistel_cipher(upper_32_bits, lower_32_bits, key):  # noqa: D103
    def to_signed_32(n):
        n = n & 0xFFFFFFFF
        return n | (-(n & 0x80000000))

    def iterate(arg1, arg2, arg3):
        return arg1 ^ (arg2 >> (32 - arg3) | to_signed_32(arg2 << arg3))

    upper = to_signed_32(upper_32_bits)
    lower = to_signed_32(lower_32_bits)

    data = (lower & 0xFFFFFFFF) | (upper << 32)

    lower2 = to_signed_32(data & 0xFFFFFFFF)
    upper2 = to_signed_32((data >> 32) & 0xFFFFFFFF)

    for i in range(16):
        v2_1 = upper2 ^ iterate(lower2, key, i)
        v8 = lower2
        lower2 = v2_1
        upper2 = v8

    return (upper2 << 32) | (lower2 & 0xFFFFFFFF)


def timestamp_to_millis(timestamp):  # noqa: D103
    return int(timestamp.timestamp() * 1000)

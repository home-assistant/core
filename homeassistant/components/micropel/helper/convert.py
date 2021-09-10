"""Convert values between different systems."""


def int_to_hex(value: int, num_of_bytes: int) -> str:
    """Convert value from int to hex string."""
    value_hex = hex(value)
    value_hex = value_hex.replace("0x", "")
    while len(value_hex) < num_of_bytes:
        value_hex = "0" + value_hex
    return value_hex.upper()

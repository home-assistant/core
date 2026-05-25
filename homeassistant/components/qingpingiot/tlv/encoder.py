"""TLV encoder for sending commands to Qingping devices."""

import logging

_LOGGER = logging.getLogger(__name__)


def int_to_bytes_little_endian(value: int, length: int, signed: bool = False) -> bytes:
    """Convert integer to little endian bytes."""
    return value.to_bytes(length, byteorder="little", signed=signed)


def encode_tlv_packet(key: int, data: bytes) -> bytes:
    """Encode a single TLV packet (key + length + data)."""
    length = len(data)
    return bytes([key]) + int_to_bytes_little_endian(length, 2) + data


def calculate_checksum(data: bytes) -> bytes:
    """Calculate checksum - sum of all bytes."""
    checksum = sum(data) & 0xFFFF
    return int_to_bytes_little_endian(checksum, 2)


def tlv_encode(command: int, packets: dict[int, bytes]) -> bytes:
    """Encode TLV command message.

    Args:
        command: Command byte (e.g., 0x02 for settings)
        packets: Dictionary of {key: data_bytes}

    Returns:
        Complete TLV message starting with 'CG'
    """
    payload = b""
    for key, data in packets.items():
        payload += encode_tlv_packet(key, data)

    # Build message: CG + command + length + payload
    message = b"CG"
    message += bytes([command])
    message += int_to_bytes_little_endian(len(payload), 2)
    message += payload

    checksum = calculate_checksum(message)
    message += checksum

    return message


def build_config_command(
    update_interval_minutes: int = 15,
    collect_interval_seconds: int = 60,
) -> bytes:
    """Build configuration command.

    Args:
        update_interval_minutes: Data upload interval in minutes (key 0x04)
        collect_interval_seconds: Data recording interval in seconds (key 0x05)
    """
    packets = {
        0x04: int_to_bytes_little_endian(update_interval_minutes, 2),
        0x05: int_to_bytes_little_endian(collect_interval_seconds, 2),
    }
    return tlv_encode(0x02, packets)


def build_offset_command(
    temperature_offset: float = 0.0,
    humidity_offset: float = 0.0,
    co2_offset: int = 0,
    pm25_offset: int = 0,
    pm10_offset: int = 0,
) -> bytes:
    """Build sensor offset command.

    Args:
        temperature_offset: Temperature offset in °C (step 0.1, key 0x46)
        humidity_offset: Humidity offset in % (step 0.1, key 0x48)
        co2_offset: CO2 offset in ppm (step 1, key 0x45)
        pm25_offset: PM2.5 offset (step 1, key 0x4B)
        pm10_offset: PM10 offset (step 1, key 0x4D)
    """
    packets: dict[int, bytes] = {}

    if temperature_offset != 0.0:
        temp_val = int(temperature_offset * 10)
        packets[0x46] = int_to_bytes_little_endian(temp_val, 2, signed=True)

    if humidity_offset != 0.0:
        hum_val = int(humidity_offset * 10)
        packets[0x48] = int_to_bytes_little_endian(hum_val, 2, signed=True)

    if co2_offset != 0:
        packets[0x45] = int_to_bytes_little_endian(co2_offset, 2, signed=True)

    if pm25_offset != 0:
        packets[0x4B] = int_to_bytes_little_endian(pm25_offset, 2, signed=True)

    if pm10_offset != 0:
        packets[0x4D] = int_to_bytes_little_endian(pm10_offset, 2, signed=True)

    if not packets:
        _LOGGER.warning("No offsets provided, creating empty command")

    return tlv_encode(0x02, packets)


def build_co2_asc_command(enable: bool) -> bytes:
    """Build CO2 ASC (Automatic Self-Calibration) command.

    Args:
        enable: True to enable, False to disable (key 0x40)
    """
    packets = {
        0x40: bytes([1 if enable else 0]),
    }
    return tlv_encode(0x02, packets)


def build_led_switch_command(enable: bool) -> bytes:
    """Build LED switch command.

    Args:
        enable: True to enable, False to disable (key 0x63)
    """
    packets = {
        0x63: bytes([1 if enable else 0]),
    }
    return tlv_encode(0x02, packets)


def build_request_settings_command() -> bytes:
    """Build command to request current device settings."""
    return tlv_encode(0x01, {})


def tlv_to_hex(tlv_data: bytes) -> str:
    """Convert TLV bytes to hex string for debugging."""
    return tlv_data.hex()

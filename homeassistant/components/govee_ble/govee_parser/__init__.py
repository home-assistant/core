"""Parser for Govee BLE advertisements.

This file is shamlessly copied from the following repository:
https://github.com/Ernst79/bleparser/blob/c42ae922e1abed2720c7fac993777e1bd59c0c93/package/bleparser/govee.py

MIT License applies.
"""
from __future__ import annotations

import logging
import struct
from typing import Any

_LOGGER = logging.getLogger(__name__)

PACKED_hHB = struct.Struct(">hHB")
PACKED_hh = struct.Struct(">hh")
PACKED_hhbhh = struct.Struct(">hhbhh")
PACKED_hhhhh = struct.Struct(">hhhhh")


def decode_temps(packet_value: int) -> float:
    """Decode potential negative temperatures."""
    # https://github.com/Thrilleratplay/GoveeWatcher/issues/2
    if packet_value & 0x800000:
        return float((packet_value ^ 0x800000) / -10000)
    return float(packet_value / 10000)


def decode_temps_probes(packet_value: int) -> float:
    """Filter potential negative temperatures."""
    if packet_value < 0:
        return 0.0
    return float(packet_value / 100)


NOT_GOVEE_MANUFACTURER = {76, 60552}


def parse_govee_from_discovery_data(
    manufacturer_data: dict[int, bytes]
) -> dict[str, Any] | None:
    """Parse Govee BLE advertisement data."""
    for device_id, mfr_data in manufacturer_data.items():
        if device_id in NOT_GOVEE_MANUFACTURER:
            continue
        if result := parse_govee(device_id, mfr_data):
            return result

    return None


def parse_govee(device_id: int, mfr_data: bytes) -> dict[str, str | int | float] | None:
    """Parser for Govee sensors."""
    # TODO: Add support for multiple sensors
    # TODO: standardize data types
    # TODO: standardize firmware version
    _LOGGER.warning("Parsing Govee sensor: %s %s", device_id, mfr_data)
    # Original messages had the device id
    # appended to the start of the mfr_data
    # This is not the case for the new messages
    # So we need to add padding to the start
    data = b"\x00" * 4 + mfr_data

    msg_length = len(data)
    firmware = "Govee"
    result: dict[str, str | int | float] = {"firmware": firmware}

    if msg_length == 10 and device_id == 0xEC88:
        device_type = "H5072/H5075"
        packet_5072_5075 = data[5:8].hex()
        packet = int(packet_5072_5075, 16)
        temp = decode_temps(packet)
        humi = float((packet % 1000) / 10)
        batt = int(data[8])
        result.update({"temperature": temp, "humidity": humi, "battery": batt})
    elif msg_length == 10 and device_id == 0x0001:
        device_type = "H5101/H5102/H5177"
        packet_5101_5102 = data[6:9].hex()
        packet = int(packet_5101_5102, 16)
        temp = decode_temps(packet)
        humi = float((packet % 1000) / 10)
        batt = int(data[9])
        result.update({"temperature": temp, "humidity": humi, "battery": batt})
    elif msg_length == 11 and device_id == 0xEC88:
        device_type = "H5074"
        (temp, humi, batt) = PACKED_hHB.unpack(data[5:10])
        result.update(
            {"temperature": temp / 100, "humidity": humi / 100, "battery": batt}
        )
    elif msg_length == 13 and device_id == 0xEC88:
        device_type = "H5051/H5071"
        (temp, humi, batt) = PACKED_hHB.unpack(data[5:10])
        result.update(
            {"temperature": temp / 100, "humidity": humi / 100, "battery": batt}
        )
    elif msg_length == 13 and device_id == 0x0001:
        packet_5178 = data[7:10].hex()
        packet = int(packet_5178, 16)
        temp = decode_temps(packet)
        humi = float((packet % 1000) / 10)
        batt = int(data[10])
        sensor_id = data[6]
        result.update(
            {
                "temperature": temp,
                "humidity": humi,
                "battery": batt,
                "sensor id": sensor_id,
            }
        )
        if sensor_id == 0:
            device_type = "H5178"
        elif sensor_id == 1:
            device_type = "H5178-outdoor"
        else:
            _LOGGER.debug(
                "Unknown sensor id for Govee H5178, please report to the developers, data: %s",
                data.hex(),
            )
    elif msg_length == 13 and device_id == 0x8801:
        device_type = "H5179"
        (temp, humi, batt) = PACKED_hHB.unpack(data[8:13])
        result.update(
            {"temperature": temp / 100, "humidity": humi / 100, "battery": batt}
        )
    elif msg_length == 18:
        device_type = "H5183"
        (temp_probe_1, temp_alarm_1) = PACKED_hh.unpack(data[12:16])
        result.update(
            {
                "temperature probe 1": decode_temps_probes(temp_probe_1),
                "temperature alarm probe 1": decode_temps_probes(temp_alarm_1),
            }
        )
    elif msg_length == 21:
        device_type = "H5182"
        (
            temp_probe_1,
            temp_alarm_1,
            _,
            temp_probe_2,
            temp_alarm_2,
        ) = PACKED_hhbhh.unpack(data[12:21])
        result.update(
            {
                "temperature probe 1": decode_temps_probes(temp_probe_1),
                "temperature alarm probe 1": decode_temps_probes(temp_alarm_1),
                "temperature probe 2": decode_temps_probes(temp_probe_2),
                "temperature alarm probe 2": decode_temps_probes(temp_alarm_2),
            }
        )
    elif msg_length == 24:
        device_type = "H5185"
        (
            temp_probe_1,
            temp_alarm_1,
            _,
            temp_probe_2,
            temp_alarm_2,
        ) = PACKED_hhhhh.unpack(data[12:22])
        result.update(
            {
                "temperature probe 1": decode_temps_probes(temp_probe_1),
                "temperature alarm probe 1": decode_temps_probes(temp_alarm_1),
                "temperature probe 2": decode_temps_probes(temp_probe_2),
                "temperature alarm probe 2": decode_temps_probes(temp_alarm_2),
            }
        )
    else:
        return None

    return result | {
        "type": device_type,
        "firmware": firmware,
    }

"""TLV decoder for Qingping devices with binary protocol."""

from datetime import datetime
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def bytes_to_int_little_endian(byte_array: bytes) -> int:
    """Convert little endian bytes to integer."""
    val = 0
    for i in range(len(byte_array)):
        val = val | byte_array[i] << i * 8
    return val


def fmt_timestamp(timestamp: int) -> str:
    """Format timestamp to human readable string."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def tlv_unpack(byte_array: bytes) -> dict[str, Any]:
    """Unpack TLV data starting with 4347 (CG)."""
    if len(byte_array) < 5:
        _LOGGER.error("Byte array too short for TLV unpacking")
        return {"cmd": None, "productId": 0, "length": 0, "subPackList": []}

    cmd = byte_array[2:3].hex()
    length = bytes_to_int_little_endian(byte_array[3:5])

    if len(byte_array) < 5 + length:
        _LOGGER.error("Byte array shorter than expected length")
        return {"cmd": cmd, "productId": 0, "length": length, "subPackList": []}

    payload = byte_array[5 : 5 + length]
    product_id = 0

    index = 0
    sub_pack_list = []

    while index < length:
        if index + 3 > length:
            _LOGGER.warning("Truncated TLV data at index %d", index)
            break

        key = payload[index : index + 1].hex()
        sub_len = bytes_to_int_little_endian(payload[index + 1 : index + 3])

        if index + 3 + sub_len > length:
            _LOGGER.warning("Sub-packet extends beyond payload at index %d", index)
            break

        sub_payload = payload[index + 3 : index + 3 + sub_len]
        index = index + 3 + sub_len

        sub_pack = {
            "key": key,
            "len": sub_len,
            "payload": sub_payload,
        }

        if key == "38":
            product_id = sub_payload[0] if len(sub_payload) > 0 else 0

        sub_pack_list.append(sub_pack)

    return {
        "cmd": cmd,
        "productId": product_id,
        "length": length,
        "subPackList": sub_pack_list,
    }


def decode_th_data(byte_array: bytes, product_id: int = 0) -> dict[str, Any]:
    """Decode temperature, humidity, pressure, and battery data."""
    if len(byte_array) < 6:
        _LOGGER.error("Byte array too short for TH data decoding")
        return {}

    th = bytes_to_int_little_endian(byte_array[0:3])
    temperature = ((th >> 12) - 500) / 10
    humidity = (th & 0xFFF) / 10
    raw_3_5 = bytes_to_int_little_endian(byte_array[3:5])
    battery = byte_array[5]

    out: dict[str, Any] = {
        "dataType": "data",
        "timestamp": 0,
        "time": "",
        "temperature": temperature,
        "humidity": humidity,
        "battery": battery,
    }

    if product_id == 51:
        out["co2"] = raw_3_5
    else:
        out["pressure"] = raw_3_5 / 100.0

    return out


def decode_realtime_data(byte_array: bytes, product_id: int = 0) -> dict[str, Any]:
    """Decode real-time sensor data."""
    if len(byte_array) < 11:
        _LOGGER.error("Byte array too short for realtime data decoding")
        return {}

    timestamp = bytes_to_int_little_endian(byte_array[0:4])
    realtime_data = decode_th_data(byte_array[4:], product_id)
    rssi = byte_array[10]
    if rssi >= 128:
        rssi -= 256

    realtime_data["dataType"] = "event"
    realtime_data["timestamp"] = timestamp
    realtime_data["time"] = fmt_timestamp(timestamp)
    realtime_data["rssi"] = rssi

    return realtime_data


def decode_history_data(byte_array: bytes, product_id: int = 0) -> list[dict[str, Any]]:
    """Decode historical sensor data."""
    if len(byte_array) < 6:
        _LOGGER.error("Byte array too short for history data decoding")
        return []

    timestamp = bytes_to_int_little_endian(byte_array[0:4])
    duration = bytes_to_int_little_endian(byte_array[4:6])

    history_data_list = []
    pack_len = 6
    index = 6
    i = 0

    while index + pack_len <= len(byte_array):
        history_pack = byte_array[index : index + pack_len]
        history_data = decode_th_data(history_pack, product_id)
        history_data["timestamp"] = timestamp + duration * i
        history_data["dataType"] = "data"
        history_data["time"] = fmt_timestamp(history_data["timestamp"])

        history_data_list.append(history_data)
        i += 1
        index += pack_len

    return history_data_list


def decode_sensor_data_v2(byte_array: bytes) -> dict[str, Any]:
    """Decode sensor data version 2 (TLV key 0x85)."""
    if len(byte_array) < 5:
        _LOGGER.error("Byte array too short for sensor data v2 decoding")
        return {}

    sensor_data = {}
    timestamp = bytes_to_int_little_endian(byte_array[0:4])
    sensor_data["timestamp"] = timestamp

    sensor_type = byte_array[4]

    if sensor_type == 1:  # Temperature + Humidity
        if len(byte_array) >= 9:
            temperature_val = bytes_to_int_little_endian(byte_array[5:7])
            humidity_val = bytes_to_int_little_endian(byte_array[7:9])
            sensor_data["temperature"] = temperature_val / 10.0
            sensor_data["humidity"] = humidity_val / 10.0

    elif sensor_type == 2:  # Temperature only
        if len(byte_array) >= 7:
            temperature_val = bytes_to_int_little_endian(byte_array[5:7])
            sensor_data["temperature"] = temperature_val / 10.0

    elif sensor_type == 3:  # Temperature + Humidity + Pressure
        if len(byte_array) >= 11:
            temperature_val = bytes_to_int_little_endian(byte_array[5:7])
            humidity_val = bytes_to_int_little_endian(byte_array[7:9])
            pressure_val = bytes_to_int_little_endian(byte_array[9:11])
            sensor_data["temperature"] = temperature_val / 10.0
            sensor_data["humidity"] = humidity_val / 10.0
            sensor_data["pressure"] = pressure_val / 100.0

    elif sensor_type == 4:  # Temperature + Humidity + CO2
        if len(byte_array) >= 11:
            temperature_val = bytes_to_int_little_endian(byte_array[5:7])
            humidity_val = bytes_to_int_little_endian(byte_array[7:9])
            co2_val = bytes_to_int_little_endian(byte_array[9:11])
            sensor_data["temperature"] = temperature_val / 10.0
            sensor_data["humidity"] = humidity_val / 10.0
            sensor_data["co2"] = co2_val

    elif sensor_type == 10:  # Full environment monitor (CGR1W, CGR1PW)
        if len(byte_array) >= 23:
            temperature_val = bytes_to_int_little_endian(byte_array[5:7])
            humidity_val = bytes_to_int_little_endian(byte_array[7:9])
            co2_val = bytes_to_int_little_endian(byte_array[9:11])
            pm25_val = bytes_to_int_little_endian(byte_array[11:13])
            pm10_val = bytes_to_int_little_endian(byte_array[13:15])
            tvoc_val = bytes_to_int_little_endian(byte_array[15:17])
            noise_val = bytes_to_int_little_endian(byte_array[17:19])
            light_val = bytes_to_int_little_endian(byte_array[19:23])

            sensor_data["temperature"] = temperature_val / 10.0
            sensor_data["humidity"] = humidity_val / 10.0
            sensor_data["co2"] = co2_val
            sensor_data["pm25"] = pm25_val
            sensor_data["pm10"] = pm10_val
            sensor_data["tvoc"] = tvoc_val
            sensor_data["noise"] = noise_val
            sensor_data["light"] = light_val

    return sensor_data


def _decode_utf8_field(payload: bytes, warning_msg: str) -> str | None:
    """Decode a UTF-8 payload field, returning None on failure."""
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        _LOGGER.warning(warning_msg)
        return None


def _decode_simple_field(key: str, payload: bytes) -> tuple[str, Any] | None:
    """Decode simple single-value fields, returning (field_name, value) or None."""
    if key == "04" and len(payload) >= 1:
        return ("reportInterval", bytes_to_int_little_endian(payload))
    if key == "05" and len(payload) >= 1:
        return ("collectInterval", bytes_to_int_little_endian(payload))
    if key == "1d" and len(payload) >= 1:
        return ("deviceStatus", payload[0])
    if key in {"64", "09"} and len(payload) >= 1:
        return ("battery", payload[0])
    if key == "65" and len(payload) >= 1:
        return ("signalStrength", bytes_to_int_little_endian(payload))
    if key == "2c" and len(payload) >= 1:
        return ("usbPluggedIn", payload[0] == 1)
    return None


_VERSION_FIELDS: dict[str, tuple[str, str]] = {
    "11": ("version", "Failed to decode version string"),
    "34": ("versionModel", "Failed to decode version model string"),
    "35": ("versionMcu", "Failed to decode version MCU string"),
}


def _decode_sub_packs(
    sub_packs: list[dict[str, Any]], product_id: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Decode sub-packs and return (out_data, data_list)."""
    out_data: dict[str, Any] = {"productId": product_id}
    data_list: list[dict[str, Any]] = []

    for sub_pack in sub_packs:
        key = sub_pack["key"]
        payload = sub_pack["payload"]

        if key == "14":
            realtime_data = decode_realtime_data(payload, product_id)
            if realtime_data:
                out_data["sensorData"] = [realtime_data]

        elif key == "03":
            history_data = decode_history_data(payload, product_id)
            if history_data:
                out_data["sensorData"] = history_data

        elif key == "85":
            sensor_data = decode_sensor_data_v2(payload)
            if sensor_data:
                data_list.append(sensor_data)

        elif key == "61":
            if len(payload) == 0:
                out_data["pmModuleConnected"] = False
            else:
                out_data["pmModuleConnected"] = True
                out_data["pmModuleSerial"] = payload.hex()

        elif key in _VERSION_FIELDS:
            field_name, warning_msg = _VERSION_FIELDS[key]
            decoded = _decode_utf8_field(payload, warning_msg)
            if decoded is not None:
                out_data[field_name] = decoded

        elif key == "2c" and len(payload) >= 1:
            out_data["batteryCharging"] = payload[0] == 1

        else:
            simple = _decode_simple_field(key, payload)
            if simple is not None:
                out_data[simple[0]] = simple[1]

    return out_data, data_list


def tlv_decode(byte_array: bytes) -> dict[str, Any]:
    """Main TLV decoder function."""
    try:
        if len(byte_array) < 2 or byte_array[0:2] != b"CG":
            _LOGGER.error("Invalid TLV data: does not start with 'CG' marker")
            return {}

        unpack_data = tlv_unpack(byte_array)
        out_data, data_list = _decode_sub_packs(
            unpack_data["subPackList"], unpack_data["productId"]
        )

        if data_list:
            out_data["sensorData"] = data_list

    except Exception:
        _LOGGER.exception("Error decoding TLV data")
        return {}
    else:
        return out_data


def is_tlv_format(payload: bytes) -> bool:
    """Check if the payload is in TLV binary format."""
    return len(payload) >= 2 and payload[0:2] == b"CG"

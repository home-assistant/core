"""Parser for Browan TBMS100 PIR sensor."""
import logging

from ...models import Sensors, SensorTypes, Uplink

_LOGGER = logging.getLogger(__name__)


def _parse_payload_tbms100_102(sensors: Sensors, payload: bytes) -> None:
    """Parse payload on FPort 102 - 000B374DB77A0400."""
    sensors.pir_status = payload[0] & 0x01 == 1
    sensors.battery_level = (25 + (payload[1] & 0x0F)) / 10
    sensors.temperature = (payload[2] & 0x7F) - 32
    sensors.time_since_last_event = int.from_bytes(payload[3:5], "little") * 60
    sensors.total_event_counter = int.from_bytes(payload[5:8], "little")


async def parse_uplink(uplink: Uplink) -> Uplink:
    """Parse binary payload depending on FPort."""
    if uplink.f_port == 102:
        _parse_payload_tbms100_102(uplink.sensors, uplink.payload)
    else:
        _LOGGER.warning("Unknown frame port {%s}", Uplink.f_port)

    return uplink


def supported_sensors() -> list:
    """Return supported measurements for this sensor."""
    return [SensorTypes.Temperature, SensorTypes.BatteryLevel]

"""Tests for the IoTaWatt integration."""
from iotawattpy.sensor import Sensor

INPUT_SENSOR = Sensor(
    channel="1",
    name="My Sensor",
    io_type="Input",
    unit="WattHours",
    value="23",
    begin="",
    mac_addr="mock-mac",
)
OUTPUT_SENSOR = Sensor(
    channel="N/A",
    name="My WattHour Sensor",
    io_type="Output",
    unit="WattHours",
    value="243",
    begin="",
    mac_addr="mock-mac",
)

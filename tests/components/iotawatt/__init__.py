"""Tests for the IoTaWatt integration."""
from iotawattpy.sensor import Sensor

INPUT_SENSOR = Sensor(
    channel="1",
    base_name="My Sensor",
    suffix=None,
    io_type="Input",
    unit="Watts",
    value=23,
    begin="",
    mac_addr="mock-mac",
)
OUTPUT_SENSOR = Sensor(
    channel="N/A",
    base_name="My WattHour Sensor",
    suffix=None,
    io_type="Output",
    unit="WattHours",
    value=243,
    begin="",
    mac_addr="mock-mac",
    fromStart=True,
)

OUTPUT_ACCUMULATED_SENSOR = Sensor(
    channel="N/A",
    base_name="My WattHour Accumulated Sensor",
    suffix=".wh",
    io_type="Output",
    unit="WattHours",
    value=200,
    begin="",
    mac_addr="mock-mac",
    fromStart=False,
)

OUTPUT_ACCUMULATED_SENSOR2 = Sensor(
    channel="N/A",
    base_name="My WattHour Accumulated Sensor2",
    suffix=".wh",
    io_type="Output",
    unit="WattHours",
    value=500,
    begin="",
    mac_addr="mock-mac",
    fromStart=False,
)

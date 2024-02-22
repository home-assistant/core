"""Constants for the Rainforest RAVEn tests."""

from aioraven.data import (
    CurrentSummationDelivered,
    DeviceInfo,
    InstantaneousDemand,
    MeterInfo,
    MeterList,
    MeterType,
    NetworkInfo,
    PriceCluster,
)
from iso4217 import Currency

from homeassistant.components import usb

DISCOVERY_INFO = usb.UsbServiceInfo(
    device="/dev/ttyACM0",
    pid="0x0003",
    vid="0x04B4",
    serial_number="1234",
    description="RFA-Z105-2 HW2.7.3 EMU-2",
    manufacturer="Rainforest Automation, Inc.",
)


DEVICE_NAME = usb.human_readable_device_name(
    DISCOVERY_INFO.device,
    DISCOVERY_INFO.serial_number,
    DISCOVERY_INFO.manufacturer,
    DISCOVERY_INFO.description,
    int(DISCOVERY_INFO.vid, 0),
    int(DISCOVERY_INFO.pid, 0),
)


DEVICE_INFO = DeviceInfo(
    device_mac_id=bytes.fromhex("abcdef0123456789"),
    install_code=None,
    link_key=None,
    fw_version="2.0.0 (7400)",
    hw_version="2.7.3",
    image_type=None,
    manufacturer=DISCOVERY_INFO.manufacturer,
    model_id="Z105-2-EMU2-LEDD_JM",
    date_code=None,
)


METER_LIST = MeterList(
    device_mac_id=DEVICE_INFO.device_mac_id,
    meter_mac_ids=[
        bytes.fromhex("1234567890abcdef"),
        bytes.fromhex("9876543210abcdef"),
    ],
)


METER_INFO = {
    None: MeterInfo(
        device_mac_id=DEVICE_INFO.device_mac_id,
        meter_mac_id=METER_LIST.meter_mac_ids[0],
        meter_type=MeterType.ELECTRIC,
        nick_name=None,
        account=None,
        auth=None,
        host=None,
        enabled=True,
    ),
    METER_LIST.meter_mac_ids[0]: MeterInfo(
        device_mac_id=DEVICE_INFO.device_mac_id,
        meter_mac_id=METER_LIST.meter_mac_ids[0],
        meter_type=MeterType.ELECTRIC,
        nick_name=None,
        account=None,
        auth=None,
        host=None,
        enabled=True,
    ),
    METER_LIST.meter_mac_ids[1]: MeterInfo(
        device_mac_id=DEVICE_INFO.device_mac_id,
        meter_mac_id=METER_LIST.meter_mac_ids[1],
        meter_type=MeterType.GAS,
        nick_name=None,
        account=None,
        auth=None,
        host=None,
        enabled=True,
    ),
}


NETWORK_INFO = NetworkInfo(
    device_mac_id=DEVICE_INFO.device_mac_id,
    coord_mac_id=None,
    status=None,
    description=None,
    status_code=None,
    ext_pan_id=None,
    channel=13,
    short_addr=None,
    link_strength=100,
)


PRICE_CLUSTER = PriceCluster(
    device_mac_id=DEVICE_INFO.device_mac_id,
    meter_mac_id=METER_INFO[None].meter_mac_id,
    time_stamp=None,
    price="0.10",
    currency=Currency.usd,
    tier=3,
    tier_label="Set by user",
    rate_label="Set by user",
)


SUMMATION = CurrentSummationDelivered(
    device_mac_id=DEVICE_INFO.device_mac_id,
    meter_mac_id=METER_INFO[None].meter_mac_id,
    time_stamp=None,
    summation_delivered="23456.7890",
    summation_received="00000.0000",
)


DEMAND = InstantaneousDemand(
    device_mac_id=DEVICE_INFO.device_mac_id,
    meter_mac_id=METER_INFO[None].meter_mac_id,
    time_stamp=None,
    demand="1.2345",
)

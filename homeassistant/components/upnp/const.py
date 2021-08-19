"""Constants for the IGD component."""
from datetime import timedelta
import logging
from typing import Dict, List, Tuple

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import DATA_BYTES, DATA_RATE_KIBIBYTES_PER_SECOND, TIME_SECONDS

LOGGER = logging.getLogger(__package__)

CONF_LOCAL_IP = "local_ip"
DOMAIN = "upnp"
DOMAIN_CONFIG = "config"
DOMAIN_DEVICES = "devices"
DOMAIN_LOCAL_IP = "local_ip"
BYTES_RECEIVED = "bytes_received"
BYTES_SENT = "bytes_sent"
PACKETS_RECEIVED = "packets_received"
PACKETS_SENT = "packets_sent"
TIMESTAMP = "timestamp"
DATA_PACKETS = "packets"
DATA_RATE_PACKETS_PER_SECOND = f"{DATA_PACKETS}/{TIME_SECONDS}"
WAN_STATUS = "wan_status"
ROUTER_IP = "ip"
ROUTER_UPTIME = "uptime"
KIBIBYTE = 1024
UPDATE_INTERVAL = timedelta(seconds=30)
CONFIG_ENTRY_SCAN_INTERVAL = "scan_interval"
CONFIG_ENTRY_ST = "st"
CONFIG_ENTRY_UDN = "udn"
CONFIG_ENTRY_HOSTNAME = "hostname"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30).total_seconds()
ST_IGD_V1 = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
ST_IGD_V2 = "urn:schemas-upnp-org:device:InternetGatewayDevice:2"
SSDP_SEARCH_TIMEOUT = 4

RAW_SENSOR = "raw_sensor"
DERIVED_SENSOR = "derived_sensor"

SENSOR_ENTITY_DESCRIPTIONS: Dict[str, List[Tuple[SensorEntityDescription, str]]] = {
    RAW_SENSOR: [
        (
            SensorEntityDescription(
                key=BYTES_RECEIVED,
                name=f"{DATA_BYTES} received",
                icon="mdi:server-network",
                native_unit_of_measurement=DATA_BYTES,
            ),
            "d",
        ),
        (
            SensorEntityDescription(
                key=BYTES_SENT,
                name=f"{DATA_BYTES} sent",
                icon="mdi:server-network",
                native_unit_of_measurement=DATA_BYTES,
            ),
            "d",
        ),
        (
            SensorEntityDescription(
                key=PACKETS_RECEIVED,
                name=f"{DATA_PACKETS} received",
                icon="mdi:server-network",
                native_unit_of_measurement=DATA_PACKETS,
            ),
            "d",
        ),
        (
            SensorEntityDescription(
                key=PACKETS_SENT,
                name=f"{DATA_PACKETS} sent",
                icon="mdi:server-network",
                native_unit_of_measurement=DATA_PACKETS,
            ),
            "d",
        ),
        (
            SensorEntityDescription(
                key=ROUTER_IP,
                name="IP",
                icon="mdi:server-network",
            ),
            "s",
        ),
        (
            SensorEntityDescription(
                key=ROUTER_UPTIME,
                name="Uptime",
                icon="mdi:server-network",
                native_unit_of_measurement=TIME_SECONDS,
                entity_registry_enabled_default=False,
            ),
            "d",
        ),
        (
            SensorEntityDescription(
                key=WAN_STATUS,
                name="wan status",
                icon="mdi:server-network",
            ),
            "s",
        ),
    ],
    DERIVED_SENSOR: [
        (
            SensorEntityDescription(
                key="KiB/sec_received",
                name=f"{DATA_RATE_KIBIBYTES_PER_SECOND} received",
                icon="mdi:server-network",
                native_unit_of_measurement=DATA_RATE_KIBIBYTES_PER_SECOND,
            ),
            ".1f",
        ),
        (
            SensorEntityDescription(
                key="KiB/sent",
                name=f"{DATA_RATE_KIBIBYTES_PER_SECOND} sent",
                icon="mdi:server-network",
                native_unit_of_measurement=DATA_RATE_KIBIBYTES_PER_SECOND,
            ),
            ".1f",
        ),
        (
            SensorEntityDescription(
                key="packets/sec_received",
                name=f"{DATA_RATE_PACKETS_PER_SECOND} received",
                icon="mdi:server-network",
                native_unit_of_measurement=DATA_RATE_PACKETS_PER_SECOND,
            ),
            ".1f",
        ),
        (
            SensorEntityDescription(
                key="packets/sent",
                name=f"{DATA_RATE_PACKETS_PER_SECOND} sent",
                icon="mdi:server-network",
                native_unit_of_measurement=DATA_RATE_PACKETS_PER_SECOND,
            ),
            ".1f",
        ),
    ],
}

BINARYSENSOR_ENTITY_DESCRIPTIONS: List[BinarySensorEntityDescription] = [
    BinarySensorEntityDescription(
        key=WAN_STATUS,
        name="wan status",
    )
]

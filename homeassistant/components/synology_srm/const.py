"""Constants used in the Synology SRM components."""

from typing import Final

DOMAIN: Final = "synology_srm"
DEFAULT_NAME: Final = "Synology SRM"
DEFAULT_API_PORT: Final = 8001
DEFAULT_DETECTION_TIME: Final = 300
DEFAULT_SSL: Final = True
DEFAULT_NODE_ID: Final = 0
DEFAULT_USERNAME: Final = "admin"

ATTR_MANUFACTURER: Final = "Synology SRM"
ATTR_SERIAL_NUMBER: Final = "serial-number"
ATTR_FIRMWARE: Final = "current-firmware"
ATTR_MODEL: Final = "model"

CONF_DETECTION_TIME: Final = "detection_time"
CONF_NODE_ID: Final = "node_id"

DEVICE_ATTRIBUTE_ALIAS: Final = {
    "band": None,
    "connection": None,
    "current_rate": None,
    "dev_type": None,
    "hostname": None,
    "ip6_addr": None,
    "ip_addr": None,
    "is_baned": "is_banned",
    "is_beamforming_on": None,
    "is_guest": None,
    "is_high_qos": None,
    "is_low_qos": None,
    "is_manual_dev_type": None,
    "is_manual_hostname": None,
    "is_online": None,
    "is_parental_controled": "is_parental_controlled",
    "is_qos": None,
    "is_wireless": None,
    "mac": None,
    "max_rate": None,
    "mesh_node_id": None,
    "rate_quality": None,
    "signalstrength": "signal_strength",
    "transferRXRate": "transfer_rx_rate",
    "transferTXRate": "transfer_tx_rate",
}

GET_SYSTEM_INFO: Final = "mesh.get_system_info"
GET_NETWORK_NSM_DEVICE: Final = "mesh.get_network_nsm_device"

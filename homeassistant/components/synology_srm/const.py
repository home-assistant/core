"""Constants for the Synology SRM integration."""

DOMAIN = "synology_srm"

DEFAULT_USERNAME = "admin"
DEFAULT_PORT = 8001
DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False

DEVICE_ICON = {
    "nas": "mdi:nas",
    "notebook": "mdi:laptop",
    "computer": "mdi:desktop-mac",
    "tv": "mdi:television",
    "printer": "mdi:printer",
    "tablet": "mdi:tablet-ipad",
    "gamebox": "mdi:gamepad-variant",
    "phone": "mdi:cellphone",
}

DEVICE_ATTRIBUTE_ALIAS = {
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

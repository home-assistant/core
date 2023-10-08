"""Data for LoRaWAN component tests."""
import pytest


@pytest.fixture
def ttn_uplink():
    """TTN uplink dict for LoRaWAN component tests."""
    return {
        "@type": "type.googleapis.com/ttn.lorawan.v3.ApplicationUp",
        "end_device_ids": {
            "device_id": "TEST-DEVICE",
            "application_ids": {"application_id": "TEST-APPLICATION"},
            "dev_eui": "0000000000000002",
            "join_eui": "0000000000000001",
        },
        "correlation_ids": [
            "as:up:01H76BQNE6FWRVNDH1QQ7ZZ047",
            "rpc:/ttn.lorawan.v3.AppAs/SimulateUplink:8a9acd3e-6095-4bc5-917a-53d821b73670",
        ],
        "received_at": "2023-08-06T21:23:29.349110781Z",
        "uplink_message": {
            "f_port": 102,
            "frm_payload": "AAs3Tbd6BAA=",
            "rx_metadata": [
                {
                    "gateway_ids": {"gateway_id": "test"},
                    "rssi": 42,
                    "channel_rssi": 42,
                    "snr": 4.2,
                }
            ],
            "settings": {
                "data_rate": {"lora": {"bandwidth": 125000, "spreading_factor": 7}},
                "frequency": "868000000",
            },
        },
    }

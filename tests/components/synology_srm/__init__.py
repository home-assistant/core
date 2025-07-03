"""Tests for the Synology SRM component."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.components import synology_srm
from homeassistant.components.synology_srm.const import (
    CONF_DETECTION_TIME,
    CONF_NODE_ID,
    DEFAULT_DETECTION_TIME,
    GET_NETWORK_NSM_DEVICE,
    GET_SYSTEM_INFO,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DATA = {
    CONF_NAME: "Synology SRM",
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_NODE_ID: 0,
    CONF_PORT: 8001,
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
}

MOCK_OPTIONS = {
    CONF_DETECTION_TIME: DEFAULT_DETECTION_TIME,
}

NODE_DATA = [
    {
        "firmware_ver": "SRM 1.3.1-9346 Update 12",
        "is_re": False,
        "model": "WRX560",
        "node_id": 0,
        "sn": "22B0VFRAN7BY7",
        "unique": "synology_hawkeye_wrx560",
        "uptime": 948463,
    }
]


DEVICE_1_ETHERNET = {
    ".id": "*1A",
    "connection": "ethernet",
    "dev_type": "default",
    "hostname": "Device_1",
    "ip6_addr": "",
    "ip_addr": "0.0.0.1",
    "is_baned": False,
    "is_beamforming_on": False,
    "is_high_qos": False,
    "is_low_qos": False,
    "is_manual_dev_type": True,
    "is_manual_hostname": False,
    "is_online": True,
    "is_parental_controled": False,
    "is_qos": False,
    "is_wireless": False,
    "mac": "00:00:00:00:00:01",
    "mesh_node_id": 0,
    "mesh_node_name": "SynologyRouter",
}
DEVICE_2_ETHERNET_OFFLINE = {
    ".id": "*1B",
    "connection": "ethernet",
    "dev_type": "default",
    "hostname": "Device_2",
    "ip6_addr": "",
    "ip_addr": "0.0.0.2",
    "is_baned": False,
    "is_beamforming_on": False,
    "is_high_qos": False,
    "is_low_qos": False,
    "is_manual_dev_type": True,
    "is_manual_hostname": False,
    "is_online": False,
    "is_parental_controled": False,
    "is_qos": False,
    "is_wireless": False,
    "mac": "00:00:00:00:00:02",
    "mesh_node_id": 0,
    "mesh_node_name": "SynologyRouter",
}
DEVICE_3_NUMERIC_NAME = {
    ".id": "*1C",
    "mac": "00:00:00:00:00:03",
    "connection": "ethernet",
    "dev_type": "default",
    "hostname": 123,
    "ip6_addr": "",
    "ip_addr": "0.0.0.3",
    "is_baned": False,
    "is_beamforming_on": False,
    "is_high_qos": False,
    "is_low_qos": False,
    "is_manual_dev_type": True,
    "is_manual_hostname": False,
    "is_online": True,
    "is_parental_controled": False,
    "is_qos": False,
    "is_wireless": False,
}

DEVICE_1_WIRELESS = {
    ".id": "*264",
    "mac": "00:00:00:00:01:01",
    "band": "2.4G",
    "connection": "wifi",
    "current_rate": 1,
    "dev_type": "default",
    "hostname": "Device_1w",
    "ip6_addr": "",
    "ip_addr": "0.0.1.1",
    "is_baned": False,
    "is_beamforming_on": False,
    "is_guest": False,
    "is_high_qos": False,
    "is_low_qos": False,
    "is_manual_dev_type": False,
    "is_manual_hostname": False,
    "is_online": False,
    "is_parental_controled": False,
    "is_qos": False,
    "is_wireless": True,
    "max_rate": 96,
    "mesh_node_id": 0,
    "mesh_node_name": "SynologyRouter",
    "rate_quality": "low",
    "signalstrength": 100,
    "transferRXRate": 0,
    "transferTXRate": 0,
    "wifi_network_id": 2,
    "wifi_profile_name": "Default",
    "wifi_ssid": "WiFli2",
}

DEVICE_2_WIRELESS = {
    **DEVICE_1_WIRELESS,
    ".id": "*265",
    "hostname": "Device_2w",
    "mac": "00:00:00:00:01:02",
    "ip_addr": "0.0.1.2",
    "is_online": True,
}
DEVICE_2_WIRELESS_OFFLINE = {
    **DEVICE_2_WIRELESS,
    "ip_addr": "",
    "is_online": False,
}
DEVICE_3_WIRELESS = {
    **DEVICE_1_WIRELESS,
    ".id": "*266",
    "hostname": "Device_3w",
    "mac": "00:00:00:00:01:03",
    "ip_addr": "0.0.1.3",
    "is_online": True,
}

DEVICE_DATA = [DEVICE_1_ETHERNET, DEVICE_2_ETHERNET_OFFLINE, DEVICE_1_WIRELESS]


async def setup_synology_srm_entry(hass: HomeAssistant, **kwargs: Any) -> None:
    """Set up Synology SRM integration successfully."""
    device_data: list[dict[str, Any]] = kwargs.get("device_data", DEVICE_DATA)
    node_data: list[dict[str, Any]] = kwargs.get("node_data", NODE_DATA)

    def mock_command(
        self,
        cmd: str,
        params: dict[str, Any] | None = None,
        suppress_errors: bool = False,
    ) -> Any:
        if cmd == GET_NETWORK_NSM_DEVICE:
            return device_data
        if cmd == GET_SYSTEM_INFO:
            return node_data
        return []

    options: dict[str, Any] = {}

    config_entry = MockConfigEntry(
        domain=synology_srm.DOMAIN, data=MOCK_DATA, options=options
    )
    config_entry.add_to_hass(hass)

    with (
        patch("synology_srm.Client"),
        patch.object(
            synology_srm.coordinator.SynologySRMData, "command", new=mock_command
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

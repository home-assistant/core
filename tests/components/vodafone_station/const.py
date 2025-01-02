"""Common stuff for Vodafone Station tests."""

from aiovodafone.api import VodafoneStationDevice

from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_USERNAME: "fake_username",
                CONF_PASSWORD: "fake_password",
            }
        ]
    }
}

MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]


DEVICE_DATA_QUERY = {
    "xx:xx:xx:xx:xx:xx": VodafoneStationDevice(
        connected=True,
        connection_type="wifi",
        ip_address="192.168.1.10",
        name="WifiDevice0",
        mac="xx:xx:xx:xx:xx:xx",
        type="laptop",
        wifi="2.4G",
    ),
}

SERIAL = "m123456789"

SENSOR_DATA_QUERY = {
    "sys_serial_number": SERIAL,
    "sys_firmware_version": "XF6_4.0.05.04",
    "sys_bootloader_version": "0220",
    "sys_hardware_version": "RHG3006 v1",
    "omci_software_version": "\t\t1.0.0.1_41032\t\t\n",
    "sys_uptime": "12:16:41",
    "sys_cpu_usage": "97%",
    "sys_reboot_cause": "Web Reboot",
    "sys_memory_usage": "51.94%",
    "sys_wireless_driver_version": "17.10.188.75;17.10.188.75",
    "sys_wireless_driver_version_5g": "17.10.188.75;17.10.188.75",
    "vf_internet_key_online_since": "",
    "vf_internet_key_ip_addr": "0.0.0.0",
    "vf_internet_key_system": "0.0.0.0",
    "vf_internet_key_mode": "Auto",
    "sys_voip_version": "v02.01.00_01.13a\n",
    "sys_date_time": "20.10.2024 | 03:44 pm",
    "sys_build_time": "Sun Jun 23 17:55:49 CST 2024\n",
    "sys_model_name": "RHG3006",
    "inter_ip_address": "1.1.1.1",
    "inter_gateway": "1.1.1.2",
    "inter_primary_dns": "1.1.1.3",
    "inter_secondary_dns": "1.1.1.4",
    "inter_firewall": "601036",
    "inter_wan_ip_address": "1.1.1.1",
    "inter_ipv6_link_local_address": "",
    "inter_ipv6_link_global_address": "",
    "inter_ipv6_gateway": "",
    "inter_ipv6_prefix_delegation": "",
    "inter_ipv6_dns_address1": "",
    "inter_ipv6_dns_address2": "",
    "lan_ip_network": "192.168.0.1/24",
    "lan_default_gateway": "192.168.0.1",
    "lan_subnet_address_subnet1": "",
    "lan_mac_address": "11:22:33:44:55:66",
    "lan_dhcp_server": "601036",
    "lan_dhcpv6_server": "601036",
    "lan_router_advertisement": "601036",
    "lan_ipv6_default_gateway": "fe80::1",
    "lan_port1_switch_mode": "1301722",
    "lan_port2_switch_mode": "1301722",
    "lan_port3_switch_mode": "1301722",
    "lan_port4_switch_mode": "1301722",
    "lan_port1_switch_speed": "10",
    "lan_port2_switch_speed": "100",
    "lan_port3_switch_speed": "1000",
    "lan_port4_switch_speed": "1000",
    "lan_port1_switch_status": "1301724",
    "lan_port2_switch_status": "1301724",
    "lan_port3_switch_status": "1301724",
    "lan_port4_switch_status": "1301724",
    "wifi_status": "601036",
    "wifi_name": "Wifi-Main-Network",
    "wifi_mac_address": "AA:BB:CC:DD:EE:FF",
    "wifi_security": "401027",
    "wifi_channel": "8",
    "wifi_bandwidth": "573",
    "guest_wifi_status": "601037",
    "guest_wifi_name": "Wifi-Guest",
    "guest_wifi_mac_addr": "AA:BB:CC:DD:EE:GG",
    "guest_wifi_security": "401027",
    "guest_wifi_channel": "N/A",
    "guest_wifi_ip": "192.168.2.1",
    "guest_wifi_subnet_addr": "255.255.255.0",
    "guest_wifi_dhcp_server": "192.168.2.1",
    "wifi_status_5g": "601036",
    "wifi_name_5g": "Wifi-Main-Network",
    "wifi_mac_address_5g": "AA:BB:CC:DD:EE:HH",
    "wifi_security_5g": "401027",
    "wifi_channel_5g": "36",
    "wifi_bandwidth_5g": "4803",
    "guest_wifi_status_5g": "601037",
    "guest_wifi_name_5g": "Wifi-Guest",
    "guest_wifi_mac_addr_5g": "AA:BB:CC:DD:EE:II",
    "guest_wifi_channel_5g": "N/A",
    "guest_wifi_security_5g": "401027",
    "guest_wifi_ip_5g": "192.168.2.1",
    "guest_wifi_subnet_addr_5g": "255.255.255.0",
    "guest_wifi_dhcp_server_5g": "192.168.2.1",
}

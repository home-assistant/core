"""Shared payloads and constants for bbox tests.

The payloads mirror the real answers of a Bbox F@st5688b running
firmware 25.1.22: endpoint answers wrapped in a single-element array
(device, wan/ip/stats), the hosts endpoint answering one entry per
network (main, guest).
"""

from http import HTTPStatus

HOST = "mabbox.bytel.fr"
API_URL = f"https://{HOST}/api/v1"
DEVICE_URL = f"{API_URL}/device"
HOSTS_URL = f"{API_URL}/hosts"
LOGIN_URL = f"{API_URL}/login"
WAN_IP_STATS_URL = f"{API_URL}/wan/ip/stats"

PASSWORD = "test-password"

UPTIME = 4861258
NUMBER_OF_BOOTS = 40
RX_BANDWIDTH = 17951
TX_BANDWIDTH = 3456
MAX_BANDWIDTH = 1000000

UNAUTHORIZED_BODY = {
    "exception": {
        "domain": "v1/hosts",
        "code": str(HTTPStatus.UNAUTHORIZED),
        "errors": [{"name": "", "reason": "Operation requires authentication"}],
    }
}

DEVICE_INFO_RESPONSE = [
    {
        "device": {
            "modelname": "F@st5688b",
            "numberofboots": NUMBER_OF_BOOTS,
            "serialnumber": "XK151000123456",
            "uptime": UPTIME,
        }
    }
]

WAN_IP_STATS_RESPONSE = [
    {
        "wan": {
            "ip": {
                "stats": {
                    "rx": {"bandwidth": RX_BANDWIDTH, "maxBandwidth": MAX_BANDWIDTH},
                    "tx": {"bandwidth": TX_BANDWIDTH, "maxBandwidth": MAX_BANDWIDTH},
                }
            }
        }
    }
]

MAIN_NETWORK_HOSTS = [
    {
        "active": 1,
        "hostname": "MyLaptop",
        "ipaddress": "192.168.1.10",
        "macaddress": "aa:bb:cc:dd:ee:01",
    },
    {
        "active": 0,
        "hostname": "OldPhone",
        "ipaddress": "192.168.1.11",
        "macaddress": "aa:bb:cc:dd:ee:02",
    },
]

GUEST_NETWORK_HOSTS = [
    {
        "active": 1,
        "guest": 1,
        "hostname": "GuestPhone",
        "ipaddress": "10.0.0.11",
        "macaddress": "aa:bb:cc:dd:ee:03",
    }
]

HOSTS_RESPONSE = [
    {"hosts": {"list": MAIN_NETWORK_HOSTS}},
    {"hosts": {"list": GUEST_NETWORK_HOSTS}},
]

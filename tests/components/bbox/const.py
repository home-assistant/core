"""Shared data for the bbox tests, mirroring a Bbox F@st5688b (fw 25.1.22)."""

from bbox_api import DeviceInfo, FirmwareVersion, Host, WANIPStats, WANStats

HOST = "mabbox.bytel.fr"
PASSWORD = "test-password"

UPTIME = 4861258
NUMBER_OF_BOOTS = 40
RX_BANDWIDTH = 17951
TX_BANDWIDTH = 3456
MAX_BANDWIDTH = 1000000

DEVICE = DeviceInfo(
    modelname="F@st5688b",
    numberofboots=NUMBER_OF_BOOTS,
    serialnumber="XK151000123456",
    uptime=UPTIME,
    running=FirmwareVersion(version="25.1.22"),
)

STATS = WANIPStats(
    rx=WANStats(bandwidth=RX_BANDWIDTH, max_bandwidth=MAX_BANDWIDTH),
    tx=WANStats(bandwidth=TX_BANDWIDTH, max_bandwidth=MAX_BANDWIDTH),
)

ACTIVE_HOST = Host(
    active=True,
    hostname="mylaptop",
    ipaddress="192.168.1.42",
    macaddress="AA:BB:CC:DD:EE:01",
)
INACTIVE_HOST = Host(
    active=False,
    hostname="oldphone",
    ipaddress="192.168.1.43",
    macaddress="AA:BB:CC:DD:EE:02",
)
NEW_HOST = Host(
    active=True,
    hostname="newtablet",
    ipaddress="192.168.1.44",
    macaddress="AA:BB:CC:DD:EE:03",
)
HOSTS = [ACTIVE_HOST, INACTIVE_HOST]

ALL_SENSORS = [
    "down_max_bandwidth",
    "up_max_bandwidth",
    "current_down_bandwidth",
    "current_up_bandwidth",
    "number_of_reboots",
    "uptime",
]

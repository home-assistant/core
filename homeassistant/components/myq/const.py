"""The MyQ integration."""
from pymyq.device import (
    STATE_CLOSED as MYQ_STATE_CLOSED,
    STATE_CLOSING as MYQ_STATE_CLOSING,
    STATE_OPEN as MYQ_STATE_OPEN,
    STATE_OPENING as MYQ_STATE_OPENING,
)

from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING

DOMAIN = "myq"

PLATFORMS = ["cover", "binary_sensor"]

MYQ_DEVICE_TYPE = "device_type"
MYQ_DEVICE_TYPE_GATE = "gate"

MYQ_DEVICE_FAMILY = "device_family"
MYQ_DEVICE_FAMILY_GATEWAY = "gateway"

MYQ_DEVICE_STATE = "state"
MYQ_DEVICE_STATE_ONLINE = "online"


MYQ_TO_HASS = {
    MYQ_STATE_CLOSED: STATE_CLOSED,
    MYQ_STATE_CLOSING: STATE_CLOSING,
    MYQ_STATE_OPEN: STATE_OPEN,
    MYQ_STATE_OPENING: STATE_OPENING,
}

MYQ_GATEWAY = "myq_gateway"
MYQ_COORDINATOR = "coordinator"

# myq has some ratelimits in place
# and 61 seemed to be work every time
UPDATE_INTERVAL = 61

# Estimated time it takes myq to start transition from one
# state to the next.
TRANSITION_START_DURATION = 7

# Estimated time it takes myq to complete a transition
# from one state to another
TRANSITION_COMPLETE_DURATION = 37

MANUFACTURER = "The Chamberlain Group Inc."

KNOWN_MODELS = {
    "00": "Chamberlain Ethernet Gateway",
    "01": "LiftMaster Ethernet Gateway",
    "02": "Craftsman Ethernet Gateway",
    "03": "Chamberlain Wi-Fi hub",
    "04": "LiftMaster Wi-Fi hub",
    "05": "Craftsman Wi-Fi hub",
    "08": "LiftMaster Wi-Fi GDO DC w/Battery Backup",
    "09": "Chamberlain Wi-Fi GDO DC w/Battery Backup",
    "10": "Craftsman Wi-Fi GDO DC 3/4HP",
    "11": "MyQ Replacement Logic Board Wi-Fi GDO DC 3/4HP",
    "12": "Chamberlain Wi-Fi GDO DC 1.25HP",
    "13": "LiftMaster Wi-Fi GDO DC 1.25HP",
    "14": "Craftsman Wi-Fi GDO DC 1.25HP",
    "15": "MyQ Replacement Logic Board Wi-Fi GDO DC 1.25HP",
    "0A": "Chamberlain Wi-Fi GDO or Gate Operator AC",
    "0B": "LiftMaster Wi-Fi GDO or Gate Operator AC",
    "0C": "Craftsman Wi-Fi GDO or Gate Operator AC",
    "0D": "MyQ Replacement Logic Board Wi-Fi GDO or Gate Operator AC",
    "0E": "Chamberlain Wi-Fi GDO DC 3/4HP",
    "0F": "LiftMaster Wi-Fi GDO DC 3/4HP",
    "20": "Chamberlain MyQ Home Bridge",
    "21": "LiftMaster MyQ Home Bridge",
    "23": "Chamberlain Smart Garage Hub",
    "24": "LiftMaster Smart Garage Hub",
    "27": "LiftMaster Wi-Fi Wall Mount opener",
    "28": "LiftMaster Commercial Wi-Fi Wall Mount operator",
    "80": "EU LiftMaster Ethernet Gateway",
    "81": "EU Chamberlain Ethernet Gateway",
}

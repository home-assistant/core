"""Constants for the PowerShades integration."""

DOMAIN = "powershades"
UDP_PORT = 42

# Protocol opcodes
OP_GET_SERIAL = 0x00
OP_SET_LIMIT = 0x01
OP_JOG_UP = 0x03
OP_JOG_DOWN = 0x04
OP_JOG_STOP = 0x05
OP_INDICATE = 0x08
OP_SET_POSITION = 0x1A
OP_GET_STATUS = 0x1D
OP_CLEAR_LIMITS = 0x1E
OP_STEP_UP = 0x23
OP_STEP_DOWN = 0x24
OP_GET_SHADE_NAME = 0x34
OP_GET_DEVICE_NAME = 0x3A

# Limit types
LIMIT_UPPER = 0x0000
LIMIT_LOWER = 0x0001

# Model byte in the Get Serial Number reply
MODEL_NAMES = {
    1: "PoE Shade",
    100: "RF Gateway",
}

# Timing
DISCOVERY_TIMEOUT = 3.0
REQUEST_TIMEOUT = 2.0
REQUEST_RETRIES = 2

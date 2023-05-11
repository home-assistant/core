"""Constants for the PID Controller integration."""
DOMAIN = "pid_controller"
PLATFORMS = ["number"]

ATTR_CYCLE_TIME = "cycle_time"
ATTR_LAST_CYCLE_START = "last_cycle_start"
ATTR_PID_ERR = "pid_error"
ATTR_PID_KP = "kp"
ATTR_PID_KI = "ki"
ATTR_PID_KD = "kd"
ATTR_PID_ENABLE = "pid_enable"
ATTR_PID_INPUT = "pid_input"
ATTR_PID_OUTPUT = "pid_output"
ATTR_PID_ERROR = "pid_error"
ATTR_INPUT1 = "input1"
ATTR_INPUT2 = "input2"
ATTR_OUTPUT = "output"
ATTR_VALUE = "value"

CONF_NUMBERS = "numbers"
CONF_CYCLE_TIME = "cycle_time"
CONF_INPUT1 = "input1"
CONF_INPUT2 = "input2"
CONF_OUTPUT = "output"
CONF_STEP = "step"
CONF_PID_KP = "kp"
CONF_PID_KI = "ki"
CONF_PID_KD = "kd"
CONF_PID_DIR = "direction"

MODE_SLIDER = "slider"
MODE_BOX = "box"
MODE_AUTO = "auto"

SERVICE_SET_KI = "set_ki"
SERVICE_SET_KP = "set_kp"
SERVICE_SET_KD = "set_kd"
SERVICE_ENABLE = "enable"

PID_DIR_DIRECT = "direct"
PID_DIR_REVERSE = "reverse"

DEFAULT_MODE = MODE_SLIDER
DEFAULT_CYCLE_TIME = {"seconds": 30}

DEFAULT_PID_DIR = PID_DIR_DIRECT
DEFAULT_PID_KI = 1.0
DEFAULT_PID_KP = 0.1
DEFAULT_PID_KD = 0.0

"""Constants for the netwave-camera integration."""

DOMAIN = "netwave"

COMMAND_STOP_MOVEMENT = "stop_movement"
COMMAND_MOVE_LEFT = "move_left"
COMMAND_MOVE_RIGHT = "move_right"
COMMAND_MOVE_UP = "move_up"
COMMAND_MOVE_DOWN = "move_down"
COMMAND_MOVE_UP_LEFT = "move_up_left"
COMMAND_MOVE_UP_RIGHT = "move_up_right"
COMMAND_MOVE_DOWN_LEFT = "move_down_left"
COMMAND_MOVE_DOWN_RIGHT = "move_down_right"
COMMAND_MOVE_CENTER = "move_center"
COMMAND_PATROL_VERTICAL = "patrol_vertical"
COMMAND_STOP_PATROL_VERTICAL = "stop_patrol_vertical"
COMMAND_PATROL_HORIZONTAL = "patrol_horizontal"
COMMAND_STOP_PATROL_HORIZONTAL = "stop_patrol_horizontal"
COMMAND_PELCO_PATROL_HORIZONTAL = "pelco_patrol_horizontal"
COMMAND_PELCO_STOP_PATROL_HORIZONTAL = "pelco_stop_patrol_horizontal"
COMMAND_TURN_IO_ON = "turn_io_on"
COMMAND_TURN_IO_OFF = "turn_io_off"
COMMAND_SET_PRESET = "set_preset"
COMMAND_RECALL_PRESET = "recall_preset"
COMMAND_RESTART_CAMERA = "restart_camera"
COMMAND_FACTORY_RESET_CAMERA = "factory_reset_camera"

PARAMETER_BRIGHTNESS = "brightness"
PARAMETER_CONTRAST = "contrast"
PARAMETER_MODE = "mode"
PARAMETER_RESOLUTION = "resolution"
PARAMETER_ORIENTATION = "orientation"

ATTR_PARAMETER = "parameter"
ATTR_VALUE = "value"
ATTR_BRIGHTNESS = "brightness"
ATTR_CONTRAST = "contrast"
ATTR_MODE = "mode"
ATTR_RESOLUTION = "resolution"
ATTR_ORIENTATION = "orientation"
ATTR_CAMERA_ALIAS = "alias"
ATTR_CAMERA_VERSION = "sys_ver"
ATTR_CAMERA_WIFI = "wifi_ssid"
ATTR_MOVE_DURATION = "move_duration"

DEFAULT_TIMEOUT = 5
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
DEFAULT_PRESET = 1
DEFAULT_NAME = "Netwave Camera"
DEFAULT_ORIENTATION = 0
DEFAULT_FRAMERATE = 2
DEFAULT_MOVE_DURATION = 0

SERVICE_COMMAND = "send_command"
SERVICE_PARAMETER = "send_parameter"
SERVICE_INFO = "refresh_info"
SERVICE_REFRESH = "refresh_complete"

CONF_VERTICAL_MIRROR = "vertical_mirror"
CONF_HORIZONTAL_MIRROR = "horizontal_mirror"
CONF_FRAMERATE = "framerate"
CONF_MOVE_DURATION = "move_duration"

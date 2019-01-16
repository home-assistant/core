"""All constants related to the ZHA component."""
import enum

DOMAIN = 'zha'

BAUD_RATES = [
    2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000
]

DATA_ZHA = 'zha'
DATA_ZHA_CONFIG = 'config'
DATA_ZHA_BRIDGE_ID = 'zha_bridge_id'
DATA_ZHA_RADIO = 'zha_radio'
DATA_ZHA_DISPATCHERS = 'zha_dispatchers'
DATA_ZHA_CORE_COMPONENT = 'zha_core_component'
DATA_ZHA_CORE_EVENTS = 'zha_core_events'
ZHA_DISCOVERY_NEW = 'zha_discovery_new_{}'

COMPONENTS = [
    'binary_sensor',
    'fan',
    'light',
    'sensor',
    'switch',
]

CONF_BAUDRATE = 'baudrate'
CONF_DATABASE = 'database_path'
CONF_DEVICE_CONFIG = 'device_config'
CONF_RADIO_TYPE = 'radio_type'
CONF_USB_PATH = 'usb_path'
DATA_DEVICE_CONFIG = 'zha_device_config'
ENABLE_QUIRKS = 'enable_quirks'

DEFAULT_RADIO_TYPE = 'ezsp'
DEFAULT_BAUDRATE = 57600
DEFAULT_DATABASE_NAME = 'zigbee.db'

ATTR_CLUSTER_ID = 'cluster_id'
ATTR_CLUSTER_TYPE = 'cluster_type'
ATTR_ATTRIBUTE = 'attribute'
ATTR_VALUE = 'value'
ATTR_MANUFACTURER = 'manufacturer'
ATTR_COMMAND = 'command'
ATTR_COMMAND_TYPE = 'command_type'
ATTR_ARGS = 'args'

IN = 'in'
OUT = 'out'
CLIENT_COMMANDS = 'client_commands'
SERVER_COMMANDS = 'server_commands'
SERVER = 'server'


class RadioType(enum.Enum):
    """Possible options for radio type."""

    ezsp = 'ezsp'
    xbee = 'xbee'

    @classmethod
    def list(cls):
        """Return list of enum's values."""
        return [e.value for e in RadioType]


DISCOVERY_KEY = 'zha_discovery_info'
DEVICE_CLASS = {}
SINGLE_INPUT_CLUSTER_DEVICE_CLASS = {}
SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS = {}
CUSTOM_CLUSTER_MAPPINGS = {}
COMPONENT_CLUSTERS = {}
EVENTABLE_CLUSTERS = []

REPORT_CONFIG_MAX_INT = 900
REPORT_CONFIG_MAX_INT_BATTERY_SAVE = 10800
REPORT_CONFIG_MIN_INT = 30
REPORT_CONFIG_MIN_INT_ASAP = 1
REPORT_CONFIG_MIN_INT_IMMEDIATE = 0
REPORT_CONFIG_MIN_INT_OP = 5
REPORT_CONFIG_MIN_INT_BATTERY_SAVE = 3600
REPORT_CONFIG_RPT_CHANGE = 1
REPORT_CONFIG_DEFAULT = (REPORT_CONFIG_MIN_INT, REPORT_CONFIG_MAX_INT,
                         REPORT_CONFIG_RPT_CHANGE)
REPORT_CONFIG_ASAP = (REPORT_CONFIG_MIN_INT_ASAP, REPORT_CONFIG_MAX_INT,
                      REPORT_CONFIG_RPT_CHANGE)
REPORT_CONFIG_BATTERY_SAVE = (REPORT_CONFIG_MIN_INT_BATTERY_SAVE,
                              REPORT_CONFIG_MAX_INT,
                              REPORT_CONFIG_RPT_CHANGE)
REPORT_CONFIG_IMMEDIATE = (REPORT_CONFIG_MIN_INT_IMMEDIATE,
                           REPORT_CONFIG_MAX_INT,
                           REPORT_CONFIG_RPT_CHANGE)
REPORT_CONFIG_OP = (REPORT_CONFIG_MIN_INT_OP, REPORT_CONFIG_MAX_INT,
                    REPORT_CONFIG_RPT_CHANGE)

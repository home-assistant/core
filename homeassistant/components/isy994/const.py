"""Constants for the ISY994 Platform."""
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL, CURRENT_HVAC_FAN, CURRENT_HVAC_HEAT, CURRENT_HVAC_IDLE,
    FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_ON, HVAC_MODE_AUTO, HVAC_MODE_COOL,
    HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY, HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF, PRESET_AWAY, PRESET_BOOST)
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR, LENGTH_CENTIMETERS, LENGTH_FEET, LENGTH_INCHES,
    LENGTH_METERS, MASS_KILOGRAMS, MASS_POUNDS, POWER_WATT, PRESSURE_INHG,
    SERVICE_LOCK, SERVICE_UNLOCK, STATE_CLOSED, STATE_CLOSING, STATE_LOCKED,
    STATE_OFF, STATE_ON, STATE_OPEN, STATE_OPENING, STATE_PROBLEM,
    STATE_UNKNOWN, STATE_UNLOCKED, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    UNIT_UV_INDEX, VOLUME_GALLONS, VOLUME_LITERS)

DOMAIN = 'isy994'

CONF_IGNORE_STRING = 'ignore_string'
CONF_SENSOR_STRING = 'sensor_string'
CONF_ENABLE_CLIMATE = 'enable_climate'
CONF_ISY_VARIABLES = 'isy_variables'
CONF_TLS_VER = 'tls'

DEFAULT_IGNORE_STRING = '{IGNORE ME}'
DEFAULT_SENSOR_STRING = 'sensor'

DEFAULT_ON_VALUE = 1
DEFAULT_OFF_VALUE = 0

KEY_ACTIONS = 'actions'
KEY_FOLDER = 'folder'
KEY_MY_PROGRAMS = 'My Programs'
KEY_STATUS = 'status'

# Do not use the Hass consts for the states here - we're matching exact API
# responses, not using them for Hass states
# Z-Wave Categories: https://www.universal-devices.com/developers/
#                      wsdk/5.0.4/4_fam.xml
NODE_FILTERS = {
    'binary_sensor': {
        'uom': [],
        'states': [],
        'node_def_id': ['BinaryAlarm', 'OnOffControl_ADV'],
        'insteon_type': ['7.13.', '16.'],  # Does a startswith() match; incl .
        'zwave_cat': (['104', '112', '138'] +
                      list(map(str, range(148, 180))))
    },
    'sensor': {
        # This is just a more-readable way of including MOST uoms between 1-100
        # (Remember that range() is non-inclusive of the stop value)
        'uom': (['1'] +
                list(map(str, range(3, 11))) +
                list(map(str, range(12, 51))) +
                list(map(str, range(52, 66))) +
                list(map(str, range(69, 78))) +
                ['79'] +
                list(map(str, range(82, 97)))),
        'states': [],
        'node_def_id': ['IMETER_SOLO'],
        'insteon_type': ['9.0.', '9.7.'],
        'zwave_cat': (['118', '143'] +
                      list(map(str, range(180, 185))))
    },
    'lock': {
        'uom': ['11'],
        'states': ['locked', 'unlocked'],
        'node_def_id': ['DoorLock'],
        'insteon_type': ['15.'],
        'zwave_cat': ['111']
    },
    'fan': {
        'uom': [],
        'states': [STATE_OFF, 'low', 'med', 'high'],
        'node_def_id': ['FanLincMotor'],
        'insteon_type': ['1.46.'],
        'zwave_cat': []
    },
    'cover': {
        'uom': ['97'],
        'states': ['open', 'closed', 'closing', 'opening', 'stopped'],
        'node_def_id': [],
        'insteon_type': [],
        'zwave_cat': []
    },
    'light': {
        'uom': ['51'],
        'states': [STATE_ON, STATE_OFF, '%'],
        'node_def_id': ['DimmerLampSwitch', 'DimmerLampSwitch_ADV',
                        'DimmerSwitchOnly', 'DimmerSwitchOnly_ADV',
                        'DimmerLampOnly', 'BallastRelayLampSwitch',
                        'BallastRelayLampSwitch_ADV',
                        'RemoteLinc2', 'RemoteLinc2_ADV'],
        'insteon_type': ['1.'],
        'zwave_cat': ['109', '119']
    },
    'switch': {
        'uom': ['2', '78'],
        'states': [STATE_ON, STATE_OFF],
        'node_def_id': ['OnOffControl', 'RelayLampSwitch',
                        'RelayLampSwitch_ADV', 'RelaySwitchOnlyPlusQuery',
                        'RelaySwitchOnlyPlusQuery_ADV', 'RelayLampOnly',
                        'RelayLampOnly_ADV', 'KeypadButton',
                        'KeypadButton_ADV', 'EZRAIN_Input', 'EZRAIN_Output',
                        'EZIO2x4_Input', 'EZIO2x4_Input_ADV', 'BinaryControl',
                        'BinaryControl_ADV', 'AlertModuleSiren',
                        'AlertModuleSiren_ADV', 'AlertModuleArmed', 'Siren',
                        'Siren_ADV'],
        'insteon_type': ['2.', '9.10.', '9.11.'],
        'zwave_cat': ['121', '122', '123', '137', '141', '147']
    },
    'climate': {
        'uom': ['2'],
        'states': ['heating', 'cooling', 'idle', 'fan_only', STATE_OFF],
        'node_def_id': ['TempLinc', 'Thermostat'],
        'insteon_type': ['5.'],
        'zwave_cat': ['140']
    }
}

SUPPORTED_DOMAINS = ['binary_sensor', 'sensor', 'lock', 'fan', 'cover',
                     'light', 'switch', 'climate']
SUPPORTED_PROGRAM_DOMAINS = ['binary_sensor', 'lock', 'fan', 'cover', 'switch']
SUPPORTED_VARIABLE_DOMAINS = ['binary_sensor', 'sensor', 'switch']

# ISY Scenes are more like Switches than Hass Scenes
# (they can turn off, and report their state)
SCENE_DOMAIN = 'switch'

ISY994_NODES = "isy994_nodes"
ISY994_WEATHER = "isy994_weather"
ISY994_PROGRAMS = "isy994_programs"
ISY994_VARIABLES = "isy994_variables"

ISY_CURRENT_TEMPERATURE = 'ST'
ISY_CURRENT_HUMIDITY = 'CLIHUM'
ISY_TARGET_TEMP_HIGH = 'CLISPC'
ISY_TARGET_TEMP_LOW = 'CLISPH'
ISY_HVAC_MODE = 'CLIMD'
ISY_HVAC_STATE = 'CLIHCS'
ISY_FAN_MODE = 'CLIFS'
ISY_UOM = 'UOM'

ISY_HVAC_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_AUTO,
    HVAC_MODE_FAN_ONLY,
]

ISY994_EVENT_FRIENDLY_NAME = {
    'OL': 'on_level',
    'RR': 'ramp_rate',
    'CLISPH': 'heat_setpoint',
    'CLISPC': 'cool_setpoint',
    'CLIFS': 'fan_state',
    'CLIHUM': 'humidity',
    'CLIHCS': 'heat_cool_state',
    'CLIEMD': 'energy_saving_mode',
    'ERR': 'device_communication_errors',
    'UOM': 'unit_of_measure',
    'TPW': 'total_kw_power',
    'PPW': 'polarized_power',
    'PF': 'power_factor',
    'CC': 'current',
    'CV': 'voltage',
    'AIRFLOW': 'air_flow',
    'ALARM': 'alarm',
    'ANGLE': 'angle_position',
    'ATMPRES': 'atmospheric_pressure',
    'BARPRES': 'barometric_pressure',
    'BATLVL': 'battery_level',
    'CLIMD': 'mode',
    'CLISMD': 'schedule_mode',
    'CLITEMP': 'temperature',
    'CO2LVL': 'co2_level',
    'CPW': 'power',
    'DISTANC': 'distance',
    'ELECRES': 'electrical_resistivity',
    'ELECCON': 'electrical_conductivity',
    'GPV': 'general_purpose',
    'GVOL': 'gas_volume',
    'LUMIN': 'luminance',
    'MOIST': 'moisture',
    'PCNT': 'pulse_count',
    'PULSCNT': 'pulse_count',
    'RAINRT': 'rain_rate',
    'ROTATE': 'rotation',
    'SEISINT': 'seismic_intensity',
    'SEISMAG': 'seismic_magnitude',
    'SOLRAD': 'solar_radiation',
    'SPEED': 'speed',
    'SVOL': 'sound_volume',
    'TANKCAP': 'tank_capacity',
    'TIDELVL': 'tide_level',
    'TIMEREM': 'time_remaining',
    'UAC': 'user_number',
    'UV': 'uv_light',
    'USRNUM': 'user_number',
    'VOCLVL': 'voc_level',
    'WEIGHT': 'weight',
    'WINDDIR': 'wind_direction',
    'WVOL': 'water_volume'
}

ISY994_EVENT_IGNORE = ['DON', 'ST', 'DFON', 'DOF', 'DFOF', 'BEEP', 'RESET',
                       'X10', 'BMAN', 'SMAN', 'BRT', 'DIM', 'BUSY']

UOM_FRIENDLY_NAME = {
    '1': 'A',
    '3': 'btu/h',
    '4': TEMP_CELSIUS,
    '5': LENGTH_CENTIMETERS,
    '6': 'ft³',
    '7': 'ft³/min',
    '8': 'm³',
    '9': 'day',
    '10': 'days',
    '12': 'dB',
    '13': 'dB A',
    '14': '°',
    '16': 'macroseismic',
    '17': TEMP_FAHRENHEIT,
    '18': LENGTH_FEET,
    '19': 'hour',
    '20': 'hours',
    '21': '%AH',
    '22': '%RH',
    '23': PRESSURE_INHG,
    '24': 'in/hr',
    '25': 'index',
    '26': 'K',
    '27': 'keyword',
    '28': MASS_KILOGRAMS,
    '29': 'kV',
    '30': 'kW',
    '31': 'kPa',
    '32': 'KPH',
    '33': ENERGY_KILO_WATT_HOUR,
    '34': 'liedu',
    '35': VOLUME_LITERS,
    '36': 'lx',
    '37': 'mercalli',
    '38': LENGTH_METERS,
    '39': 'm³/hr',
    '40': 'm/s',
    '41': 'mA',
    '42': 'ms',
    '43': 'mV',
    '44': 'min',
    '45': 'min',
    '46': 'mm/hr',
    '47': 'month',
    '48': 'MPH',
    '49': 'm/s',
    '50': 'Ω',
    '51': '%',
    '52': MASS_POUNDS,
    '53': 'pf',
    '54': 'ppm',
    '55': 'pulse count',
    '57': 's',
    '58': 's',
    '59': 'S/m',
    '60': 'm_b',
    '61': 'M_L',
    '62': 'M_w',
    '63': 'M_S',
    '64': 'shindo',
    '65': 'SML',
    '69': VOLUME_GALLONS,
    '71': UNIT_UV_INDEX,
    '72': 'V',
    '73': POWER_WATT,
    '74': 'W/m²',
    '75': 'weekday',
    '76': '°',
    '77': 'year',
    '82': 'mm',
    '83': 'km',
    '85': 'Ω',
    '86': 'kΩ',
    '87': 'm³/m³',
    '88': 'Water activity',
    '89': 'RPM',
    '90': 'Hz',
    '91': '°',
    '92': '° South',
    '102': 'kWs',
    '103': '$',
    '104': '¢',
    '105': LENGTH_INCHES,
    '106': 'mm/day'
}

UOM_TO_STATES = {
    '11': {  # Deadbolt Status
        '0': STATE_UNLOCKED,
        '100': STATE_LOCKED,
        '101': STATE_UNKNOWN,
        '102': STATE_PROBLEM,
    },
    '15': {  # Door Lock Alarm
        '1': 'master code changed',
        '2': 'tamper code entry limit',
        '3': 'escutcheon removed',
        '4': 'key/manually locked',
        '5': 'locked by touch',
        '6': 'key/manually unlocked',
        '7': 'remote locking jammed bolt',
        '8': 'remotely locked',
        '9': 'remotely unlocked',
        '10': 'deadbolt jammed',
        '11': 'battery too low to operate',
        '12': 'critical low battery',
        '13': 'low battery',
        '14': 'automatically locked',
        '15': 'automatic locking jammed bolt',
        '16': 'remotely power cycled',
        '17': 'lock handling complete',
        '19': 'user deleted',
        '20': 'user added',
        '21': 'duplicate pin',
        '22': 'jammed bolt by locking with keypad',
        '23': 'locked by keypad',
        '24': 'unlocked by keypad',
        '25': 'keypad attempt outside schedule',
        '26': 'hardware failure',
        '27': 'factory reset'
    },
    '66': {  # Thermostat Heat/Cool State
        '0': CURRENT_HVAC_IDLE,
        '1': CURRENT_HVAC_HEAT,
        '2': CURRENT_HVAC_COOL,
        '3': CURRENT_HVAC_FAN,
        '4': CURRENT_HVAC_HEAT,  # Pending Heat
        '5': CURRENT_HVAC_COOL,  # Pending Cool
        # >6 defined in ISY but not implemented, leaving for future expanision.
        '6': 'vent',
        '7': 'aux heat',
        '8': '2nd stage heating',
        '9': '2nd stage cooling',
        '10': '2nd stage aux heat',
        '11': '3rd stage aux heat'
    },
    '67': {  # Thermostat Mode
        '0': HVAC_MODE_OFF,
        '1': HVAC_MODE_HEAT,
        '2': HVAC_MODE_COOL,
        '3': HVAC_MODE_AUTO,
        '4': PRESET_BOOST,
        '5': 'resume',
        '6': HVAC_MODE_FAN_ONLY,
        '7': 'furnace',
        '8': HVAC_MODE_DRY,
        '9': 'moist air',
        '10': 'auto changeover',
        '11': 'energy save heat',
        '12': 'energy save cool',
        '13': PRESET_AWAY
    },
    '68': {  # Thermostat Fan Mode
        '0': FAN_AUTO,
        '1': FAN_ON,
        '2': FAN_HIGH,  # Auto High
        '3': FAN_HIGH,
        '4': FAN_MEDIUM,  # Auto Medium
        '5': FAN_MEDIUM,
        '6': 'circulation',
        '7': 'humidity circulation'
    },
    '78': {  # 0-Off 100-On
        '0': STATE_OFF,
        '100': STATE_ON
    },
    '79': {  # 0-Open 100-Close
        '0': STATE_OPEN,
        '100': STATE_CLOSED
    },
    '80': {  # Thermostat Fan Run State
        '0': STATE_OFF,
        '1': STATE_ON,
        '2': 'on high',
        '3': 'on medium',
        '4': 'circulation',
        '5': 'humidity circulation',
        '6': 'right/left circulation',
        '7': 'up/down circulation',
        '8': 'quiet circulation'
    },
    '84': {  # Secure Mode
        '0': SERVICE_LOCK,
        '1': SERVICE_UNLOCK
    },
    '93': {  # Power Management Alarm
        '1': 'power applied',
        '2': 'ac mains disconnected',
        '3': 'ac mains reconnected',
        '4': 'surge detection',
        '5': 'volt drop or drift',
        '6': 'over current detected',
        '7': 'over voltage detected',
        '8': 'over load detected',
        '9': 'load error',
        '10': 'replace battery soon',
        '11': 'replace battery now',
        '12': 'battery is charging',
        '13': 'battery is fully charged',
        '14': 'charge battery soon',
        '15': 'charge battery now'
    },
    '94': {  # Appliance Alarm
        '1': 'program started',
        '2': 'program in progress',
        '3': 'program completed',
        '4': 'replace main filter',
        '5': 'failure to set target temperature',
        '6': 'supplying water',
        '7': 'water supply failure',
        '8': 'boiling',
        '9': 'boiling failure',
        '10': 'washing',
        '11': 'washing failure',
        '12': 'rinsing',
        '13': 'rinsing failure',
        '14': 'draining',
        '15': 'draining failure',
        '16': 'spinning',
        '17': 'spinning failure',
        '18': 'drying',
        '19': 'drying failure',
        '20': 'fan failure',
        '21': 'compressor failure'
    },
    '95': {  # Home Health Alarm
        '1': 'leaving bed',
        '2': 'sitting on bed',
        '3': 'lying on bed',
        '4': 'posture changed',
        '5': 'sitting on edge of bed'
    },
    '96': {  # VOC Level
        '1': 'clean',
        '2': 'slightly polluted',
        '3': 'moderately polluted',
        '4': 'highly polluted'
    },
    '97': {  # Barrier Status
        **{
            '0': STATE_CLOSED,
            '100': STATE_OPEN,
            '101': STATE_UNKNOWN,
            '102': 'stopped',
            '103': STATE_CLOSING,
            '104': STATE_OPENING
            },
        **{str(b): '{} %'.format(b) for a, b in \
           enumerate(list(range(1, 100)))}  # 1-99 are percentage open
    },
    '98': {  # Insteon Thermostat Mode
        '0': HVAC_MODE_OFF,
        '1': HVAC_MODE_HEAT,
        '2': HVAC_MODE_COOL,
        '3': HVAC_MODE_HEAT_COOL,
        '4': HVAC_MODE_FAN_ONLY,
        '5': HVAC_MODE_AUTO,  # Program Auto
        '6': HVAC_MODE_AUTO,  # Program Heat-Set @ Local Device Only
        '7': HVAC_MODE_AUTO   # Program Cool-Set @ Local Device Only
    },
    '99': {  # Insteon Thermostat Fan Mode
        '7': FAN_ON,
        '8': FAN_AUTO
    }
}

HA_HVAC_TO_ISY = {
    HVAC_MODE_OFF: '0',
    HVAC_MODE_HEAT: '1',
    HVAC_MODE_COOL: '2',
    HVAC_MODE_HEAT_COOL: '3',
    HVAC_MODE_FAN_ONLY: '4',
    HVAC_MODE_AUTO: '5'
}

HA_FAN_TO_ISY = {
    FAN_ON: '7',
    FAN_AUTO: '8'
}

SUPPORTED_BIN_SENS_CLASSES = ['moisture', 'opening', 'motion', 'climate']

ISY_BIN_SENS_DEVICE_TYPES = {
    'moisture': ['16.8', '16.13', '16.14'],
    'opening': ['16.9', '16.6', '16.7', '16.2', '16.17', '16.20', '16.21'],
    'motion': ['16.1', '16.4', '16.5', '16.3'],
    'climate': ['5.11', '5.10']
}

ZWAVE_BIN_SENS_DEVICE_TYPES = {
    'safety': ['137', '172', '176', '177', '178'],
    'smoke': ['138', '156'],
    'problem': ['148', '149', '157', '158', '164', '174', '175'],
    'gas': ['150', '151'],
    'sound': ['153'],
    'cold': ['152', '168'],
    'heat': ['154', '166', '167'],
    'moisture': ['159', '169'],
    'door': ['160'],
    'battery': ['162'],
    'motion': ['155'],
    'vibration': ['173']
}

INSTEON_RAMP_RATES = {
    '0': '9 min',
    '1': '8 min',
    '2': '7 min',
    '3': '6 min',
    '4': '5 min',
    '5': '4.5 min',
    '6': '4 min',
    '7': '3.5 min',
    '8': '3 min',
    '9': '2.5 min',
    '10': '2 min',
    '11': '1.5 min',
    '12': '1 min',
    '13': '47 s',
    '14': '43 s',
    '15': '38.5 s',
    '16': '34 s',
    '17': '32 s',
    '18': '30 s',
    '19': '28 s',
    '20': '26 s',
    '21': '23.5 s',
    '22': '21.5 s',
    '23': '19 s',
    '24': '8.5 s',
    '25': '6.5 s',
    '26': '4.5 s',
    '27': '2 s',
    '28': '0.5 s',
    '29': '0.3 s',
    '30': '0.2 s',
    '31': '0.1 s'
}

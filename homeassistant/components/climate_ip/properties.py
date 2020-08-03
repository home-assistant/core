import json
import homeassistant.helpers.config_validation as cv
from homeassistant.util.temperature import convert as convert_temperature
from .yaml_const import (
    CONFIG_DEVICE_STATUS_TEMPLATE, CONFIG_DEVICE_CONNECTION_TEMPLATE, CONFIG_DEVICE_VALIDATION_TEMPLATE,
    CONFIG_TYPE, CONFIG_DEVICE_CONNECTION, CONFIG_DEVICE_OPERATION_VALUES, CONFIG_DEVICE_OPERATION_VALUE, 
    CONFIG_DEVICE_OPERATION_NUMBER_MIN, CONFIG_DEVICE_OPERATION_NUMBER_MAX, CONFIG_DEVICE_OPERATION_TEMP_UNIT_TEMPLATE,
    )

from .connection import (Connection)

from homeassistant.const import (
    STATE_UNKNOWN, STATE_OFF, STATE_ON, TEMP_CELSIUS, TEMP_FAHRENHEIT, 
)

CLIMATE_IP_PROPERTIES = []
CLIMATE_IP_STATUS_GETTER = []

PROPERTY_TYPE_MODE = 'modes'
PROPERTY_TYPE_SWITCH = 'switch'
PROPERTY_TYPE_NUMBER = 'number'
PROPERTY_TYPE_TEMP = 'temperature'
STATUS_GETTER_JSON = 'json_status'

UNIT_MAP = {
    'C': TEMP_CELSIUS,
    'c': TEMP_CELSIUS,
    'Celsius': TEMP_CELSIUS,
    'F': TEMP_FAHRENHEIT,
    'f': TEMP_FAHRENHEIT,
    'Fahrenheit': TEMP_FAHRENHEIT,
    TEMP_CELSIUS: TEMP_CELSIUS,
    TEMP_FAHRENHEIT: TEMP_FAHRENHEIT,
}

test_json = {'Devices':[{'Alarms':[{'alarmType':'Device','code':'FilterAlarm','id':'0','triggeredTime':'2019-02-25T08:46:01'}],'ConfigurationLink':{'href':'/devices/0/configuration'},'Diagnosis':{'diagnosisStart':'Ready'},'EnergyConsumption':{'saveLocation':'/files/usage.db'},'InformationLink':{'href':'/devices/0/information'},'Mode':{'modes':['Auto'],'options':['Comode_Off','Sleep_0','Autoclean_Off','Spi_Off','FilterCleanAlarm_0','OutdoorTemp_63','CoolCapa_35','WarmCapa_40','UsagesDB_254','FilterTime_10000','OptionCode_54458','UpdateAllow_0','FilterAlarmTime_500','Function_15','Volume_100'],'supportedModes':['Cool','Dry','Wind','Auto']},'Operation':{'power':'Off'},'Temperatures':[{'current':22.0,'desired':25.0,'id':'0','maximum':30,'minimum':16,'unit':'Celsius'}],'Wind':{'direction':'Fix','maxSpeedLevel':4,'speedLevel':0},'connected':True,'description':'TP6X_RAC_16K','id':'0','name':'RAC','resources':['Alarms','Configuration','Diagnosis','EnergyConsumption','Information','Mode','Operation','Temperatures','Wind'],'type':'Air_Conditioner','uuid':'C0972729-EB73-0000-0000-000000000000'}]}

def register_property(dev_prop):
    """Decorate a function to register a propery."""
    CLIMATE_IP_PROPERTIES.append(dev_prop)
    return dev_prop

def register_status_getter(getter):
    """Decorate a function to register a status getter."""
    CLIMATE_IP_STATUS_GETTER.append(getter)
    return getter

def create_property(name, node, connection_base):
    for prop in CLIMATE_IP_PROPERTIES:
        if CONFIG_TYPE in node:
            if prop.match_type(node[CONFIG_TYPE]):
                op = prop(name, connection_base)
                if op.load_from_yaml(node):
                    return op
    return None

def create_status_getter(name, node, connection_base):
    for getter in CLIMATE_IP_STATUS_GETTER:
        if CONFIG_TYPE in node:
            if getter.match_type(node[CONFIG_TYPE]):
                g = getter(name, connection_base)
                if g.load_from_yaml(node):
                    return g
    return None

class DeviceProperty:
    def __init__(self, name, connection):
        self._name = name
        self._value = STATE_UNKNOWN
        self._connection = connection
        self._status_template = None
        self._id = name
        self._connection_template = None
        self._validation_template = None
        self._device_state = None

    @property
    def id(self):
        return self._id

    def is_valid(self, device_state):
        self._device_state = device_state
        if self.validation_template == None or device_state == None:
            return True
        else:
            try:
                v = self.validation_template.render(device_state=device_state)
                return str(v).lower() == 'valid'
            except:
                return False
            return False
    
    @property
    def config_validation_type(self):
        return cv.string

    @property
    def status_template(self):
        return self._status_template

    @property
    def value(self):
        return self._value

    @property
    def name(self):
        return self._name

    def get_connection(self, value):
        return self._connection

    @property
    def connection_template(self):
        return self._connection_template

    @property
    def validation_template(self):
        return self._validation_template

    def load_from_yaml(self, node):
        """Load configuration from yaml node dictionary. Return True if successful False otherwise."""
        from jinja2 import Template
        if node is not None:
            if CONFIG_DEVICE_STATUS_TEMPLATE in node:
                self._status_template = Template(node[CONFIG_DEVICE_STATUS_TEMPLATE])
            if CONFIG_DEVICE_CONNECTION_TEMPLATE in node:
                self._connection_template = Template(node[CONFIG_DEVICE_CONNECTION_TEMPLATE])
            if CONFIG_DEVICE_VALIDATION_TEMPLATE in node:
                self._validation_template = Template(node[CONFIG_DEVICE_VALIDATION_TEMPLATE])
            self._connection = self._connection.create_updated(node.get(CONFIG_DEVICE_CONNECTION, {}))
            return True
        return False

    def convert_dev_to_hass(self, dev_value):
        """Convert device state value to HASS."""
        return dev_value
    
    def update_state(self, device_state, debug):
        """Update property from device state and return current value."""
        self._device_state = device_state
        v = STATE_UNKNOWN
        if self.status_template is not None and device_state is not None:
            v = self.status_template.render(device_state=device_state)
        if v is not STATE_UNKNOWN:
            self._value = self.convert_dev_to_hass(v)
        return self.value
 
    @property
    def state_attributes(self):
        """Return dictionary with property attributes."""
        return { self.id : self.value }

@register_status_getter
class GetJsonStatus(DeviceProperty):
    def __init__(self, name, connection):
        super(GetJsonStatus, self).__init__(name, connection)
        self._json_status = None
        self._attrs = {}

    @staticmethod
    def match_type(type):
        return type == STATUS_GETTER_JSON

    def update_state(self, device_state, debug):
        self._device_state = device_state
        device_state = self.get_connection(None).execute(self.connection_template, None, device_state)
        self._value = device_state
        self._json_status = device_state
        if device_state is not None:
            self._attrs = { 'device_state' : json.dumps(device_state) }
            if self.status_template is not None:
                try:
                    v = self.status_template.render(device_state=device_state)
                    v = v.replace("'", '"')
                    v = v.replace("True", '"True"')
                    self._value = json.loads(v)
                except:
                    pass # do nothing
        else:
            self._attrs = { 'device_state' : None }

        return self.value

    @property
    def state_attributes(self):
        """Return dictionary with property attributes."""
        return self._attrs


class DeviceOperation(DeviceProperty):
    def __init__(self, name, connection):
        super(DeviceOperation, self).__init__(name, connection)

    def set_value(self, v):
        """Set device property value."""
        resp = self.get_connection(v).execute(self.connection_template, self.convert_hass_to_dev(v), self._device_state)
        return resp is not None

    def match_value(self, value):
        """Check if value match to operation. True if value is correct."""
        return False

    def convert_hass_to_dev(self, hass_value):
        """Convert HASS state value to device state."""
        return hass_value

class BasicDeviceOperation(DeviceOperation):
    def __init__(self, name, connection):
        super(BasicDeviceOperation, self).__init__(name, connection)
        self._values_dev_to_ha_map = {}
        self._values_ha_to_dev_map = {}
        self._values = []
        self._value_connections_map = {}

    def get_connection(self, value):
        return self._value_connections_map.get(value, self._connection)

    def load_from_yaml(self, node):
        """Load configuration from yaml node dictionary. Return True if successful False otherwise."""
        if super(BasicDeviceOperation, self).load_from_yaml(node):
            if node is not None:
                node_values = node.get(CONFIG_DEVICE_OPERATION_VALUES, {})
                if len(node_values) == 0:
                    return False
                
                for ha_value in node_values.keys():
                    node_value = node_values[ha_value]
                    r = self._connection.create_updated(node_value.get(CONFIG_DEVICE_CONNECTION, {}))
                    self._value_connections_map[ha_value] = r
                    self._values.append(ha_value)
                    if CONFIG_DEVICE_OPERATION_VALUE in node_value:
                        dev_value = node_value[CONFIG_DEVICE_OPERATION_VALUE]
                        self._values_dev_to_ha_map[dev_value] = ha_value
                        self._values_ha_to_dev_map[ha_value] = dev_value
                
                return True
        return False

    @property
    def values(self):
        return self._values

    def match_value(self, value):
        """Check if value match to operation. True if value is correct."""
        return value in self._values_ha_to_dev_map  

    def convert_dev_to_hass(self, dev_value):
        """Convert device state value to HASS."""
        return self._values_dev_to_ha_map.get(dev_value, dev_value)
    
    def convert_hass_to_dev(self, ha_value):
        """Convert HASS state value to device state."""
        return self._values_ha_to_dev_map.get(ha_value, ha_value)

@register_property
class ModeOperation(BasicDeviceOperation):
    def __init__(self, name, connection):
        super(ModeOperation, self).__init__(name, connection)
        self._id = name + '_mode'
 
    @staticmethod
    def match_type(type):
        return type == PROPERTY_TYPE_MODE

    @property
    def state_attributes(self):
        """Return dictionary with property attributes."""
        data = {}
        data[self.id] = self.value
        data[self.name + '_modes'] = self.values
        return data

@register_property
class SwitchOperation(BasicDeviceOperation):
    def __init__(self, name, connection):
        super(SwitchOperation, self).__init__(name, connection)
 
    @staticmethod
    def match_type(type):
        return type == PROPERTY_TYPE_SWITCH

    def load_from_yaml(self, node):
        """Load configuration from yaml node dictionary. Return True if successful False otherwise."""
        if super(SwitchOperation, self).load_from_yaml(node):
            if STATE_OFF in self._values_ha_to_dev_map:
                self._values_ha_to_dev_map[False] = self._values_ha_to_dev_map[STATE_OFF]
            if STATE_ON in self._values_ha_to_dev_map:
                self._values_ha_to_dev_map[True] = self._values_ha_to_dev_map[STATE_ON]
            return True

        return False

class BasicNumericOperation(DeviceOperation):
    def __init__(self, name, connection):
        super(BasicNumericOperation, self).__init__(name, connection)
        self._min = None
        self._max = None
        self._value = 0.0
 
    @property
    def value(self):
        f = 0
        try:
            f = float(self._value)
        except:
            f = None
        return f

    @property
    def config_validation_type(self):
        return cv.positive_int

    def match_value(self, value):
        """Check if value match to operation. True if value is correct."""
        try:
            return self.convert_hass_to_dev(float(value)) == value
        except ValueError:
            return False
    
    def load_from_yaml(self, node):
        """Load configuration from yaml node dictionary. Return True if successful False otherwise."""
        if not super(BasicNumericOperation, self).load_from_yaml(node):
            return False

        if node is not None:
            self._min = node.get(CONFIG_DEVICE_OPERATION_NUMBER_MIN, None)
            self._max = node.get(CONFIG_DEVICE_OPERATION_NUMBER_MAX, None)
            return True

        return False

    def convert_hass_to_dev(self, hass_value):
        """Convert HASS state value to device state."""
        if self._min is not None and hass_value < self._min:
            return self._min
        if self._max is not None and hass_value > self._max:
            return self._max
        
        return hass_value

@register_property
class NumericOperation(BasicNumericOperation):
    def __init__(self, name, connection):
        super(NumericOperation, self).__init__(name, connection)
 
    @staticmethod
    def match_type(type):
        return type == PROPERTY_TYPE_NUMBER


@register_property
class TemperatureOperation(BasicNumericOperation):
    def __init__(self, name, connection):
        super(TemperatureOperation, self).__init__(name, connection)
        self._unit_template = None
        self._unit = TEMP_CELSIUS

    @staticmethod
    def match_type(type):
        return type == PROPERTY_TYPE_TEMP

    def load_from_yaml(self, node):
        from jinja2 import Template
        """Load configuration from yaml node dictionary. Return True if successful False otherwise."""
        if not super(TemperatureOperation, self).load_from_yaml(node):
            return False

        if node is not None and CONFIG_DEVICE_OPERATION_TEMP_UNIT_TEMPLATE in node:
            self._unit_template = Template(node[CONFIG_DEVICE_OPERATION_TEMP_UNIT_TEMPLATE])
        return True

    def update_state(self, device_state, debug):
        if self._unit_template is not None and device_state is not None:
            try:
                unit = self._unit_template.render(device_state=device_state)
                if unit in UNIT_MAP:
                    self._unit = UNIT_MAP[unit]
            except:
                pass # skip temperature unit rendering
        
        return super(TemperatureOperation, self).update_state(device_state, debug)
 
    def convert_dev_to_hass(self, dev_value):
        """Convert device state value to HASS."""
        return convert_temperature(float(dev_value), self._unit, TEMP_CELSIUS)
    
    def convert_hass_to_dev(self, hass_value):
        v =  hass_value
        """Convert HASS state value to device state."""
        if self._min is not None and hass_value < self._min:
            v = self._min
        if self._max is not None and hass_value > self._max:
            v = self._max
        
        return convert_temperature(float(v), TEMP_CELSIUS, self._unit)

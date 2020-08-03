from .connection import (
    register_connection,
    Connection,
)
from .yaml_const import (
    CONFIG_DEVICE_CONNECTION_PARAMS, CONF_CERT, CONFIG_DEVICE_CONNECTION, CONFIG_DEVICE_CONDITION_TEMPLATE,
)
from homeassistant.const import (CONF_PORT, CONF_TOKEN, CONF_MAC, CONF_IP_ADDRESS)
import json
import logging
import os
import traceback
import time

CONNECTION_TYPE_REQUEST = 'request'
CONNECTION_TYPE_REQUEST_PRINT = 'request_print'

class ConnectionRequestBase(Connection):
    def __init__(self, hass_config, logger):
        super(ConnectionRequestBase, self).__init__(hass_config, logger)
        self._params = { 'timeout' : 5 }
        self._embedded_command = None
        logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
        self.update_configuration_from_hass(hass_config)
        self._condition_template = None

    @property
    def embedded_command(self):
        return self._embedded_command

    @property
    def condition_template(self):
        return self._condition_template

    def update_configuration_from_hass(self, hass_config):
        if hass_config is not None:
            cert_file = hass_config.get(CONF_CERT, None)
            if cert_file is not None:
                if cert_file.find('\\') == -1 and cert_file.find('/') == -1:
                    cert_file = os.path.join(os.path.dirname(__file__), cert_file)

            self._params[CONF_CERT] = cert_file

    def load_from_yaml(self, node, connection_base):
        from jinja2 import Template
        if connection_base:
            self._params.update(connection_base._params.copy())
            self._condition_template = connection_base._condition_template
        
        if node:
            self._params.update(node.get(CONFIG_DEVICE_CONNECTION_PARAMS, {}))
            if CONFIG_DEVICE_CONNECTION in node:
                self._embedded_command = self.create_updated(node[CONFIG_DEVICE_CONNECTION])
            if CONFIG_DEVICE_CONDITION_TEMPLATE in node:
                self._condition_template = Template(node[CONFIG_DEVICE_CONDITION_TEMPLATE])
        
        return True

    def check_execute_condition(self, device_state):
        do_execute = True
        self.logger.info("Checking execute condition")
        if self.condition_template is not None:
            self.logger.info("Execute condition found, evaluating")
            try:
                rendered_condition = self.condition_template.render(device_state = device_state)
                self.logger.info("Execute condition evaluated: {0}".format(rendered_condition))
                do_execute = rendered_condition == '1'
            except:
                self.logger.error("Execute condition found, error while evaluating, executing command")
                do_execute = True
        else:
            self.logger.warning("Execute condition not found, executing")
    
        return do_execute

    def execute_internal(self, template, value, device_state) -> (json, bool, int):
        import requests, warnings
        from requests.packages.urllib3.exceptions import InsecureRequestWarning

        params = self._params
        if template is not None:
            params.update(json.loads(template.render(value=value)))
        
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=InsecureRequestWarning)
            with requests.sessions.Session() as session:
                self.logger.info(self._params)
                try:
                    resp = session.request(**self._params)
                    self.logger.info("Command executed with code: {}, text: {}".format(resp.status_code, resp.text))
                except:
                    # something goes wrong, print callstack and return None
                    self.logger.error("Request execution failed. Stack trace:")
                    traceback.print_exc()
                    return (None, False, 0)

        if resp and resp.ok:
            if resp.status_code == 200:
                try:
                    j = resp.json()
                    return (j, True, resp.status_code)
                except:
                    self.logger.warning("Parsing response json failed!")
            else:
                return ({}, True, resp.status_code)

        elif resp:
            self.logger.error("Execution failed, status code: {}, text: {}".format(resp.status_code, resp.text))
            return (None, False, resp.status_code)
        else:
            self.logger.error("Execution failed, unknown error")
        
        return (None, False, 0)

    def execute(self, template, value, device_state):
        if self.embedded_command:
            self.logger.info("Embedded command found, executing...")
            self.embedded_command.execute(template, value, device_state)

        if not self.check_execute_condition(device_state):
            self.logger.info("Execute condition not met, skipping command")
            return ({}, True, 200)

        self.logger.info("Executing command...")
        j, ok, code = self.execute_internal(template, value, device_state)
        if not j and 500 <= code < 505:
            # server error, try again
            time.sleep(1.0)
            j = self.execute_internal(template, value, device_state)[0]
        
        return j

@register_connection
class ConnectionRequest(ConnectionRequestBase):
    def __init__(self, hass_config, logger):
        super(ConnectionRequest, self).__init__(hass_config, logger)

    @staticmethod
    def match_type(type):
        return type == CONNECTION_TYPE_REQUEST

    def create_updated(self, node):
        c = ConnectionRequest(None, self.logger)
        c.load_from_yaml(node, self)
        return c

test_json = {'Devices' : [{'Alarms':[{'alarmType':'Device','code':'FilterAlarm','id':'0','triggeredTime':'2019-02-25T08:46:01'}],'ConfigurationLink':{'href':'/devices/0/configuration'},'Diagnosis':{'diagnosisStart':'Ready'},'EnergyConsumption':{'saveLocation':'/files/usage.db'},'InformationLink':{'href':'/devices/0/information'},'Mode':{'modes':['Auto'],'options':['Comode_Off','Sleep_0','Autoclean_Off','Spi_Off','FilterCleanAlarm_0','OutdoorTemp_63','CoolCapa_35','WarmCapa_40','UsagesDB_254','FilterTime_10000','OptionCode_54458','UpdateAllow_0','FilterAlarmTime_500','Function_15','Volume_100'],'supportedModes':['Cool','Dry','Wind','Auto']},'Operation':{'power':'Off'},'Temperatures':[{'current':22.0,'desired':25.0,'id':'0','maximum':30,'minimum':16,'unit':'Celsius'}],'Wind':{'direction':'Fix','maxSpeedLevel':4,'speedLevel':0},'connected':True,'description':'TP6X_RAC_16K','id':'0','name':'RAC','resources':['Alarms','Configuration','Diagnosis','EnergyConsumption','Information','Mode','Operation','Temperatures','Wind'],'type':'Air_Conditioner','uuid':'00000000-0000-0000-0000-000000000000' } ] }

@register_connection
class ConnectionRequestPrint(ConnectionRequestBase):
    def __init__(self, hass_config, logger):
        super(ConnectionRequestPrint, self).__init__(hass_config, logger)

    @staticmethod
    def match_type(type):
        return type == CONNECTION_TYPE_REQUEST_PRINT

    def create_updated(self, node):
        c = ConnectionRequestPrint(None, self.logger)
        c.load_from_yaml(node, self)
        return c

    def execute_internal(self, template, value, device_state) -> (json, bool, int):
        self.logger.info("ConnectionRequestPrint, execute with params: {}".format(self._params))
        return (test_json, True, 200)

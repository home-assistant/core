"""
Support for Tahoma devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tahoma/
"""
import logging
import json
import requests
import voluptuous as vol

from collections import defaultdict
from homeassistant.util import (convert, slugify)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import Entity
from homeassistant.exceptions import HomeAssistantError

TAHOMA_CONTROLLER = None

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tahoma'
_BASE_URL = 'https://www.tahomalink.com/enduser-mobile-web/externalAPI/json/'
_BASE_HEADERS = { 'User-Agent' : 'mine',  }
CONF_EXCLUDE = 'exclude'

TAHOMA_ID_LIST_SCHEMA = vol.Schema([cv.string])

TAHOMA_DEVICES = defaultdict(list)
TAHOMA_ID_FORMAT = '{}_{}'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_EXCLUDE, default=[]): TAHOMA_ID_LIST_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """docstring for async_setup"""
    global TAHOMA_CONTROLLER
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    exclude  = conf.get(CONF_EXCLUDE)
        
    TAHOMA_CONTROLLER = TahomaApi(username, password)
    TAHOMA_DEVICES['api'] = TAHOMA_CONTROLLER
    
    TAHOMA_CONTROLLER.getSetup()
    devices = TAHOMA_CONTROLLER.getDevices()
    user = TAHOMA_CONTROLLER.getUser()
    
    actionGroups = TAHOMA_CONTROLLER.getActionGroups()

    for    device in devices:
        d = TAHOMA_CONTROLLER.getDevice(device)
        _LOGGER.error(d.label)
        _LOGGER.error(d.type)
        if any(ext not in d.type for ext in exclude):
            device_type = map_tahoma_device(d)
            if device_type is None:
                continue
            TAHOMA_DEVICES[device_type].append(d)


    return True

def map_tahoma_device(tahoma_device):
    """Map tahoma classes to Home Assistant types."""
    if tahoma_device.type.lower().find("shutter") != -1:
        return 'cover'
    elif tahoma_device.type == 'io:LightIOSystemSensor':
        return 'sensor'
    return None

    
class TahomaApi :
    
    def __init__(self, userName, userPassword, **kwargs):
        
        """Initalize the Tahoma protocol.
        :param userName: Tahoma username
        :param userPassword: Password
        :param kwargs: Ignore, only for unit test reasons
        """
        self.__devices = {}
        self.__gateway = {}
        self.__location = {}
        self.__cookie = ""
        self.__loggedIn = False
        self.__username = userName
        self.__password = userPassword
        self.login()

    def login(self):
        if self.__loggedIn:
            return
        login = { 'userId' : self.__username, 'userPassword' : self.__password }
        header = _BASE_HEADERS.copy()
        request = requests.post(_BASE_URL + 'login', data=login, headers=header)
        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for login, " +
                "protocol error: " + request.status_code + ' - ' + 
                request.reason + "(" + e + ")")
        
        if 'error' in result.keys():
            raise HomeAssistantError("Could not login: " + result['error'])
        
        if request.status_code != 200:
            raise HomeAssistantError("Could not login, HTTP code: " + 
                str(request.status_code) + ' - ' + request.reason)
        
        if 'success' not in result.keys() or not result['success']:
            raise HomeAssistantError("Could not login, no success")
        
        cookie = request.headers.get("set-cookie")
        if cookie is None:
            raise HomeAssistantError("Could not login, no cookie set")
        
        self.__cookie = cookie
        self.__loggedIn = True
        return self.__loggedIn

    def getUser(self):
        """ Get the user informations from the server.
        :return: a dict with all the informations
        :rtype: dict

        raises ValueError in case of protocol issues

        :Example:
        
        >>> "creationTime": <time>,
        >>> "lastUpdateTime": <time>,
        >>> "userId": "<email for login>",
        >>> "title": 0,
        >>> "firstName": "<First>",
        >>> "lastName": "<Last>",
        >>> "email": "<contact email>",
        >>> "phoneNumber": "<phone>",
        >>> "mobilePhone": "<mobile>",
        >>> "locale": "<two char country code>"

        :Warning:

        The type and amount of values in the dictionary can change any time.
        """

        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.get(_BASE_URL + 'getEndUser', headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.getUser()
            return

        try:
            result = request.json()
        except ValueError:
            raise HomeAssistantError("Not a valid result for" + 
                " getEndUser, protocol error!")

        return result['endUser']

    def getSetup(self):
        """Load the setup from the server.

        Loads the configuration from the server, nothing will be returned. After loading the configuration the devices
        can be obtained through getDevice and getDevices. Also location and gateway will be set through this
        method.

        raises ValueError in case of protocol issues

        :Seealso:

        - getDevice
        - getDevices
        - location
        - gateway
        """

        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.get(_BASE_URL + 'getSetup', headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.getSetup()
            return
            #raise ValueError('Could not get setup, HTTP code: ' + str(request.status_code) + ' - ' + request.reason)

        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for getSetup, " + 
                "protocol error: " + e)

        self._getSetup(result)

    def _getSetup(self, result):
        """ Internal method which process the 
            results from the server."""
        self.__devices = {}

        if ('setup' not in result.keys() 
            or 'devices' not in result['setup'].keys()):
            raise HomeAssistantError("Did not find device definition.")

        for deviceData in result['setup']['devices']:
            device = Device(self, deviceData)
            self.__devices[device.url] = device

        self.__location = result['setup']['location']
        self.__gateway = result['setup']['gateways']

    @property
    def location(self):
        """Return the location information stored in your Tahoma box.

        When the configuration has been loaded via getSetup this 
        method retrieves all the location details which have
        been saved for your Tahoma box.

        :return: a dict with all the informations
        :rtype: dict

        :Example:

        >>> "creationTime": <time>,
        >>> "lastUpdateTime": <time>,
        >>> "addressLine1": "<street>",
        >>> "postalCode": "<zip>",
        >>> "city": "<city>",
        >>> "country": "<country>",
        >>> "timezone": "Europe/<city>",
        >>> "longitude": 2.343,
        >>> "latitude": 48.857,
        >>> "twilightMode": 2,
        >>> "twilightCity": "<city>",
        >>> "summerSolsticeDuskMinutes": 1290,
        >>> "winterSolsticeDuskMinutes": 990,
        >>> "twilightOffsetEnabled": False,
        >>> "dawnOffset": 0,
        >>> "duskOffset": 0

        :Warning:

        The type and amount of values in the dictionary can change any time.

        :Seealso:

        - getSetup
        """
        return self.__location

    @property
    def gateway(self):
        """Return information about your Tahoma box.

        When the configuration has been loaded via getSetup this 
        method retrieves all  details your Tahoma box.

        :return: a list of all gateways with a dict per gateway with 
        all the informations
        :rtype: list

        :Example:

        >>> [{
        >>>     "gatewayId": "1234-1234-1234",
        >>>     "type": 15,
        >>>     "placeOID": "12345678-1234-1234-1234-12345678",
        >>>     "alive": True,
        >>>     "timeReliable": True,
        >>>     "connectivity": {
        >>>         "status": "OK",
        >>>         "protocolVersion": "8"
        >>>     },
        >>>     "upToDate": True,
        >>>     "functions": "INTERNET_AUTHORIZATION,SCENARIO_DOWNLOAD,
                SCENARIO_AUTO_LAUNCHING,SCENARIO_TELECO_LAUNCHING,
                INTERNET_UPLOAD,INTERNET_UPDATE,TRIGGERS_SENSORS",
        >>>     "mode": "ACTIVE"
        >>> }]

        :Warning:

        The type and amount of values in the dictionary can change any time.

        :Seealso:

        - getSetup
        """
        return self.__gateway

    def getDevices(self):
        """Return all devices which have been found with last getSetup 
        request.

        With a previous getSetup call the devices which have 
        been found will be returned.

        :return: Returns a dictionary { deviceURL -> Device }
        :rtype: dict

        :Seealso:

        - getSetup
        """
        return self.__devices

    def getDevice(self, url):
        """Return a particular device which have been found with the 
        last getSetup request.

        :param url: The device URL of the device to be returned.
        :return: Return the device identified by url or None
        :rtype: Device

        :Seealso:

        - getSetup
        """
        return self.__devices[url]

    def applyActions(self, nameOfAction, actions):
        """Start to execute an action or a group of actions.

        This method takes a bunch of actions and runs them on your 
        Tahoma box.

        :param nameOfAction: the label/name for the action
        :param actions: an array of Action objects
        :return: the execution identifier  ************** what if it fails
        :rtype: string

        raises ValueError in case of protocol issues

        :Seealso:

        - getEvents
        - getCurrentExecutions
        """

        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        actionsSerialized = []

        for action in actions:
            actionsSerialized.append(action.serialize())

        data = { "label": nameOfAction, "actions": actionsSerialized }
        js = json.dumps(data, indent=None, sort_keys=True)

        request = requests.post(_BASE_URL + "apply", headers=header, data=js)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.applyActions(nameOfAction, actions)
            return

        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for applying an " +
                "action, protocol error: " + request.status_code + ' - ' + 
                request.reason + " (" + e + ")")

        if 'execId' not in result.keys():
            raise HomeAssistantError("Could not run actions, missing execId.")

        return result['execId']

    def getEvents(self):
        """Returns a set of events which have been occured 
        since the last call of this method.

        This method should be called regulary to get all occuring 
        Events. There are three different Event types/classes
        which can be returned:

        - DeviceStateChangedEvent, if any device changed it's state 
        due to an applied action or just because of other reasons
        - CommandExecutionStateChangedEvent, a executed command goes 
        through several phases which can be followed
        - ExecutionStateChangedEvent, ******** todo

        :return: an array of Events or empty array
        :rtype: list

        raises ValueError in case of protocol issues

        :Seealso:

        - applyActions
        - launchActionGroup
        - getHistory
        """

        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.post(_BASE_URL + 'getEvents', headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.getEvents()
            return

        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for getEvent," +
                " protocol error: " + e)

        return self._getEvents(result)

    def _getEvents(self, result):
        """"Internal method for being able to run unit tests."""
        events = []

        for eventData in result:
            event = Event.factory(eventData)

            if event is not None: # otherwise it is an unknown event
                events.append(event)

                if isinstance(event, DeviceStateChangedEvent):
                    # change device state
                    if self.__devices[event.deviceURL] is None:
                        raise HomeAssistantError("Received device change " + 
                            "state for unknown device '" + 
                            event.deviceURL + "'")

                    self.__devices[event.deviceURL].setActiveStates(
                        event.states)

        return events

    def getCurrentExecutions(self):
        """Get all current running executions.

        :return: Returns a set of running Executions or empty list.
        :rtype: list

        raises ValueError in case of protocol issues

        :Seealso:

        - applyActions
        - launchActionGroup
        - getHistory
        """

        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.get(_BASE_URL + 
            'getCurrentExecutions', headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.getCurrentExecutions()
            return

        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for" + 
                " getCurrentExecutions, protocol error: " + e)

        if 'executions' not in result.keys():
            return None

        executions = []

        for executionData in result['executions']:
            exe = Execution(executionData)
            executions.append(exe)

        return executions

    def getHistory(self):
        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.get(_BASE_URL + 'getHistory', headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.getHistory()
            return

        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for" +
                " getHistory, protocol error: " + e)

        return result['history']


    def cancelAllExecutions(self):
        """Cancels all running executions.

        raises ValueError in case of any protocol issues.
        """
        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.get(_BASE_URL + 'cancelExecutions', headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.cancelAllExecutions()
            return

    def getActionGroups(self):
        """

        :return:
        """

        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.get(_BASE_URL + "getActionGroups", headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.getActionGroups()
            return

        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for " + 
                "getActionGroups, protocol error: " + e)

        if 'actionGroups' not in result.keys():
            return None

        groups = []

        for groupData in result['actionGroups']:
            group = ActionGroup(groupData)
            groups.append(group)

        return groups

    def launchActionGroup(self, id):
        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.get(_BASE_URL + 'launchActionGroup?oid=' + id, 
            headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.launchActionGroup(id)
            return

        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for launch " + 
                "action group, protocol error: " + request.status_code + 
                ' - ' + request.reason + " (" + e + ")")

        if 'actionGroup' not in result.keys():
            raise HomeAssistantError("Could not launch action" + 
                " group, missing execId.")

        return result['actionGroup'][0]['execId']

    def getStates(self, devices):
        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        js = self._createGetStateRequest(devices)

        request = requests.post(_BASE_URL + 'getStates', 
            headers=header, data=js)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.getStates(devices)
            return

        try:
            result = request.json()
        except ValueError as e:
            raise HomeAssistantError("Not a valid result for" + 
                " getStates, protocol error: " + e)

        self._getStates(result)

    def _createGetStateRequest(self, givenDevices):
        devList = []

        if isinstance(givenDevices, list):
            devices = givenDevices
        else:
            devices = []
            for devName  in self.__devices.keys():
                devices.append(self.__devices[devName])

        for device in devices:
            states = []

            for stateName in sorted(device.activeStates.keys()):
                states.append({ 'name': stateName })

            devList.append({ 'deviceURL': device.url, 'states': states })

        return json.dumps(devList, indent=None, sort_keys=True, 
            separators=(',', ': '))

    def _getStates(self, result):

        if 'devices' not in result.keys():
            return

        for deviceStates in result['devices']:
            device = self.__devices[deviceStates['deviceURL']]

            device.setActiveStates(deviceStates['states'])

    def refreshAllStates(self):
        header = _BASE_HEADERS.copy()
        header['Cookie'] = self.__cookie

        request = requests.get(_BASE_URL + "refreshAllStates", 
            headers=header)

        if request.status_code != 200:
            self.__loggedIn = False
            self.login()
            self.refreshAllStates()
            return


class TahomaDevice(Entity):
    """Representation of a Tahoma device entity."""
    def __init__(self, tahoma_device, controller):
        """Initialize the device."""
        self.tahoma_device = tahoma_device
        self.controller = controller
        # Append device id to prevent name clashes in HA.
        # self.tahoma_id = tahoma_device.url
        self.tahoma_id = TAHOMA_ID_FORMAT.format(
            slugify(tahoma_device.label), slugify(tahoma_device.url))
        self._name = self.tahoma_device.label
    
    @property
    def name(self):
        """Return the name of the device."""
        return self._name
    
    @property
    def should_poll(self):
        """Get polling requirement from tahoma device."""
        return True
    
    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['Tahoma Device Id'] = self.tahoma_device.url

        return attr


class Device:

    def __init__(self, protocol, dataInput):

        self.__protocol = protocol
        self.__rawData = dataInput

        debugOutput = json.dumps(dataInput)
        
        if 'label' not in dataInput.keys():
            raise ValueError('No device name found: ' + debugOutput)

        self.__label = dataInput['label']

        if 'controllableName' not in dataInput.keys():
            raise ValueError('No control label name found: ' + debugOutput)

        self.__type = dataInput['controllableName']

        if 'deviceURL' not in dataInput.keys():
            raise ValueError('No control URL: ' + debugOutput)

        self.__url = dataInput['deviceURL']

        # Parse definitions

        if 'definition' not in dataInput.keys():
            raise ValueError('No device definition found: ' + debugOutput)

        self.__definitions = {
            'commands': [],
            'states': []
        }

        definition = dataInput['definition']

        if 'commands' in definition.keys():
            for command in definition['commands']:
                if command['commandName'] in self.__definitions['commands']:
                    raise ValueError("Command '" + command['commandName'] +
                        "' double defined - " + debugOutput)

                self.__definitions['commands'].append(command['commandName'])

        if 'states' in definition.keys():
            for state in definition['states']:
                if state['qualifiedName'] in self.__definitions['states']:
                    raise ValueError("State '" + state['qualifiedName'] +
                        "' double defined - " + debugOutput)

                self.__definitions['states'].append(state['qualifiedName'])

        # Parse active states

        # calculate the amount of known active states
        activeStatesAmount = 0
        if 'states' in dataInput.keys():
            for state in dataInput['states']:
                activeStatesAmount += 1

        # make sure there are not more active states than definitions
        if activeStatesAmount > len(self.stateDefinitions):
            raise ValueError(
                "Missmatch of state definition and active states (" +
                    str(len(self.stateDefinitions)) + "/" +
                    str(activeStatesAmount) + "): " + debugOutput)

        if len(self.stateDefinitions) > 0:

            if 'states' not in dataInput.keys():
                raise ValueError("No active states given.")

            self.__activeStates = {}

            for state in dataInput['states']:

                if state['name'] not in self.stateDefinitions:
                    raise ValueError(
                        "Active state '" + state['name'] +
                        "' has not been defined: " + debugOutput)

                if state['name'] in self.__activeStates.keys():
                    raise ValueError(
                        "Active state '" + state['name'] +
                        "' has been double defined: " + debugOutput)

                self.__activeStates[state['name']] = state['value']

    @property
    def label(self):
        return self.__label

    @property
    def commandDefinitions(self):
        return self.__definitions['commands']

    @property
    def stateDefinitions(self):
        return self.__definitions['states']

    @property
    def activeStates(self):
        return self.__activeStates

    def setActiveState(self, name, value):
        if name not in self.__activeStates.keys():
            raise ValueError("Can not set unknown state '" + name + "'")

        if (isinstance(self.__activeStates[name], int) and
                isinstance(value, str)):
            # we get an update as str but current value is
            # an int, try to convert
            self.__activeStates[name] = int(value)
        elif (isinstance(self.__activeStates[name], float) and
                isinstance(value, str)):
            # we get an update as str but current value is
            # a float, try to convert
            self.__activeStates[name] = float(value)
        else:
            self.__activeStates[name] = value

    def setActiveStates(self, states):
        for state in states:
            self.setActiveState(state['name'], state['value'])

    @property
    def type(self):
        return self.__type

    @property
    def url(self):
        return self.__url

    def executeAction(self, action):
        self.__protocol


class Action:

    def __init__(self, data):

        self.__commands = []

        if isinstance(data, dict):
            self.__deviceURL = data['deviceURL']

            for cmd in data['commands']:
                if 'parameters' in cmd.keys():
                    self.__commands.append(
                        Command(cmd['name'], cmd['parameters']))
                else:
                    self.__commands.append(Command(cmd['name']))
        elif isinstance(data, str):
            self.__deviceURL = data
        else:
            self.__deviceURL = ""

    @property
    def deviceURL(self):
        return self.__deviceURL

    @deviceURL.setter
    def deviceURL(self, url):
        self.__deviceURL = url

    def addCommand(self, cmdName, *args):
        self.__commands.append(Command(cmdName, args))

    @property
    def commands(self):
        return self.__commands

    def serialize(self):
        commands = []

        for cmd in self.commands:
            commands.append(cmd.serialize())

        out = {'commands': commands, 'deviceURL': self.__deviceURL}

        return out

    def __str__(self):
        return json.dumps(
            self.serialize(),
            indent=4,
            sort_keys=True,
            separators=(',', ': ')
            )

    def __repr__(self):
        return json.dumps(
            self.serialize(),
            indent=None,
            sort_keys=True,
            separators=(',', ': '))


class Command:

    def __init__(self, cmdName, *args):
        self.__name = cmdName

        if len(args):
            for arg in args[0]:
                if (type(arg) is not str and
                        type(arg) is not int and
                        type(arg) is not float):
                    raise ValueError(
                        "Type '" + type(arg) + "' is not Int, bool or .")

            self.__args = args[0]
        else:
            self.__args = []

    @property
    def name(self):
        return self.__name

    @property
    def parameter(self):
        return self.__args

    def serialize(self):
        return {'name': self.__name, 'parameters': self.__args}

    def __str__(self):
        return json.dumps(
            self.serialize(),
            indent=4,
            sort_keys=True,
            separators=(',', ': '))

    def __repr__(self):
        return json.dumps(
            self.serialize(),
            indent=None,
            sort_keys=True,
            separators=(',', ': '))


class ActionGroup:

    def __init__(self, data):
        self.__lastUpdate = data['lastUpdateTime']
        self.__name = data['label']

        self.__actions = []

        for cmd in data['actions']:
            self.__actions.append(Action(cmd))

    @property
    def lastUpdate(self):
        return self.__lastUpdate

    @property
    def name(self):
        return self.__name

    @property
    def actions(self):
        return self.__actions


class Event:

    @staticmethod
    def factory(data):
        if data['name'] is "DeviceStateChangedEvent":
            return DeviceStateChangedEvent(data)
        elif data['name'] is "ExecutionStateChangedEvent":
            return ExecutionStateChangedEvent(data)
        elif data['name'] is "CommandExecutionStateChangedEvent":
            return CommandExecutionStateChangedEvent(data)
        else:
            raise ValueError("Unknown event '" + data['name'] + "' occurred.")


class DeviceStateChangedEvent(Event):

    def __init__(self, data):

        self.__deviceURL = data['deviceURL']
        self.__states = data['deviceStates']

    @property
    def deviceURL(self):
        return self.__deviceURL

    @property
    def states(self):
        return self.__states


class CommandExecutionStateChangedEvent(Event):
    def __init__(self, data):

        self.__execId = data['execId']
        self.__deviceURL = data['deviceURL']

        try:
            self.__state = EventState(int(data['newState']))
        except ValueError:
            self.__state = EventState.Unknown

        if self.__state == EventState.Failed:
            self.__failureType = data['failureType']
        else:
            self.__failureType = None

    @property
    def execId(self):
        return self.__execId

    @property
    def deviceURL(self):
        return self.__deviceURL

    @property
    def state(self):
        return self.__state

    @property
    def failureType(self):
        return self.__failureType


class ExecutionStateChangedEvent(Event):

    def __init__(self, data):

        self.__execId = data['execId']

        try:
            self.__state = EventState(int(data['newState']))
        except ValueError:
            self.__state = EventState.Unknown

        if self.__state == EventState.Failed:
            self.__failureType = data['failureType']
            fail = data['failedCommands']['command']['deviceURL']
            self.__failedDeviceURL = fail
        else:
            self.__failureType = None
            self.__failedDeviceURL = None

    @property
    def execId(self):
        return self.__execId

    @property
    def state(self):
        return self.__state

    @property
    def failureType(self):
        return self.__failureType

    @property
    def failureDeviceURL(self):
        return self.__failedDeviceURL


class EventState():

    def __init__(self, state):

        if isinstance(state, int):
            if state is EventState.Unknown0:
                self.__state = EventState.Unknown0
            elif state is EventState.NotTransmitted:
                self.__state = EventState.NotTransmitted
            elif state is EventState.Unknown2:
                self.__state = EventState.Unknown2
            elif state is EventState.Unknown3:
                self.__state = EventState.Unknown3
            elif state is EventState.Completed:
                self.__state = EventState.Completed
            elif state is EventState.Failed:
                self.__state = EventState.Failed
            elif state is EventState.Unknown:
                self.__state = EventState.Unknown
            else:
                raise ValueError("Unknown state init " + str(state))
        elif isinstance(state, str):
            # more states are missing
            if state is "NOT_TRANSMITTED":
                self.__state = EventState.NotTransmitted
            elif state is "COMPLETED":
                self.__state = EventState.Completed
            elif state is "FAILED":
                self.__state = EventState.Failed
            else:
                raise ValueError("Unknown state init '" + state + "'")
        else:
            raise ValueError(
                "EventState init can only be called with int or str.")

    @property
    def state(self):
        return self.__state

    def __int__(self):
        return self.__state

    # python > 3
    def __eq__(self, other):
        if isinstance(other, int):
            return self.__state == other
        if isinstance(other, EventState):
            return self.__state == other.__state

        return False

    # several names still missing
    Unknown0 = 0
    NotTransmitted = 1
    Unknown2 = 2
    Unknown3 = 3
    Completed = 4
    Failed = 5
    Unknown = 6


class Execution:

    def __init__(self, data):
        self.__id = data['id']
        self.__startTime = data['startTime']
        self.__state = EventState(data['state'])
        self.__name = data['actionGroup']['label']

        self.__actions = []

        for cmd in data['actionGroup']['actions']:
            self.__actions.append(Action(cmd))

    @property
    def id(self):
        return self.__id

    @property
    def startTime(self):
        return self.__startTime

    @property
    def state(self):
        return self.__state

    @property
    def name(self):
        return self.__name

    @property
    def actions(self):
        return self.__actions

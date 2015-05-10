"""
A generic switch that can be created by other componenets during setup

The switch works by listening and firing various events to communicate with
the parent entity.  The parent entity must implement discoverability in
order to create the switches.  To create a child_switch from your parent
entity you can do the following:

NOTE: the following examples use the camera component for demonstration
you will need to change the values for you particular component

STEP 1: Add you component a switch discoverable
In the switch component __init__.py file add the following you component
to the DISCOVERY_PLATFORMS dictionary, eg:

DISCOVERY_PLATFORMS = {
    camera.DISCOVER_SWITCHES: 'child_switch',
}

and also add import your compnent, eg:
import homeassistant.components.camera as camera

STEP 2: Set up switch discoverability in your component
In you component you need to fire the discovery event on entity creation.

def setup(hass, config):
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    for entity_id in component.entities.keys():
        entity = component.entities[entity_id]
        entity.add_child_component_listeners()

        data = {}
        data['entity_id'] = entity_id
        data[ATTR_DOMAIN] = DOMAIN
        data['name'] = entity.name + ' Record'
        data['parent_action'] = SWITCH_ACTION_RECORD
        data['callback_service'] = SERVICE_CAMERA
        data['callback_event'] = entity_id + EVENT_CALLBACK_RECORD
        data['listen_event'] = entity_id + EVENT_CHANGE_RECORD
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                      {ATTR_SERVICE: DISCOVER_SWITCHES,
                       ATTR_DISCOVERED: data})

The parameters:

- entity_id
This is the entity_id of the parent entity

- name
The name of the child component

-parent_action
A string defining the action the switch is for which will be passed
to your service when it is called by the child entity

-callback_service
The name of the service the child will call when turned on or off

-callback_event
The event that will be fired when the child is successfully created

-listen_event
This is the name of the event that the child will listen to for state
changes from the parent


STEP 3: Create a service for the turn on and turn off events
In the setup function of your component define the service that will
be called when your switch is toggled, eg:

def handle_motion_detection_service(service):

    target_cameras = component.extract_from_service(service)

    for camera in target_cameras:
        if action == SWITCH_ACTION_RECORD:
            if (state == STATE_ON and not
                    camera.is_recording):
                camera.record_stream()
            elif (state == STATE_OFF and
                    camera.is_recording):
                camera.stop_recording()

        camera.update_ha_state(True)

hass.services.register(
    DOMAIN,
    SERVICE_CAMERA,
    handle_motion_detection_service)


STEP 4: Listen for child creation
Inside you entity class you need to set up listeners for the
child creation events.  The callback event will fire on the
successfull creation of the child entity, eg:

def add_child_component_listeners(self):
    self.hass.bus.listen(
        self.entity_id + EVENT_CALLBACK_RECORD,
        self.process_switch_creation)

STEP 5: Notify the child switch of parent state changes
Add a function to your entity that fires an event for a particular
state change.  You can then call this function whenever you want to
notify the child switches state, eg:

def send_recording_state(self):
    state = STATE_OFF
    if self.is_recording:
        state = STATE_ON

    self.hass.bus.fire(
        self.entity_id + EVENT_CHANGE_RECORD,
        {
            'entity_id': self.entity_id,
            'state': state
        })

If everything goes according to plan you will now see the additonal
switch on the UI.  For a complete working example check out the camera
component's __init__.py

"""
import logging

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.loader import get_component

from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID,
    ATTR_DOMAIN, EVENT_STATE_CHANGED)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the GenericSwitch platform. """
    logger = logging.getLogger(__name__)

    if discovery_info is not None:
        parent_domain = discovery_info.get(ATTR_DOMAIN, None)
        parent_component = get_component(parent_domain)

        if parent_component is None:
            logger.error(
                'Could not find parent component {0}'.format(parent_domain))
            return

        parent_entity_id = discovery_info.get('entity_id', None)
        name = discovery_info.get('name', parent_entity_id + ' Switch')

        devices = []
        devices.append(ChildSwitch(hass, name, discovery_info))
        add_devices(devices)

        # Notify any parent devices that this device was created
        for device in devices:
            hass.bus.fire(
                device.callback_event,
                {
                    'entity_id': device.entity_id,
                    'parent_action': device._parent_action
                })

    return True


# pylint: disable=too-many-instance-attributes
class ChildSwitch(ToggleEntity):
    """ A generic switch the can be created during setup of another component
    and will watch the state of a specified variable """
    def __init__(self, hass, name, info=None, state=STATE_OFF):
        info = {} if info is None else info
        self._state = state
        self._name = name
        self._info = info
        self._parent_entity_id = info.get('entity_id', None)
        self._parent_entity_domain = info.get(ATTR_DOMAIN, None)
        self._parent_action = info.get('parent_action', None)
        self._callback_service = info.get('callback_service', None)
        self.hass = hass
        self._logger = logging.getLogger(__name__)
        self._callback_event = info.get('callback_event', None)
        self._listen_event = info.get('listen_event', None)

        self.hass.bus.listen(
            self._listen_event,
            self.process_parent_entity_change)


    def process_parent_entity_change(self, event):
        """ Handle changes to the state of the linked parent entity """
        if not event or not event.data:
            return
        new_state_value = event.data.get('state')

        if self._state != new_state_value:
            self._state = new_state_value
            self.update_ha_state(True)

    @property
    def name(self):
        """ Returns the name of the entity. """
        return self._name

    @property
    def is_on(self):
        """ True if entity is on. """
        return True if self._state == STATE_ON else False

    def turn_on(self, **kwargs):
        """ Turn the entity on. """
        self._state = STATE_ON
        self.call_parent_service()

    def turn_off(self, **kwargs):
        """ Turn the entity off. """
        self._state = STATE_OFF
        self.call_parent_service()

    def call_parent_service(self):
        """ Calls the specified service to send state """
        service_data = {}
        service_data[ATTR_ENTITY_ID] = self._parent_entity_id
        service_data['action'] = self._parent_action
        service_data['state'] = self._state
        self.hass.services.call(
            self._parent_entity_domain,
            self._callback_service,
            service_data)

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        attr = super().state_attributes
        attr['parent_entity_id'] = self._parent_entity_id
        attr['parent_entity_domain'] = self._parent_entity_domain
        attr['parent_action'] = self._parent_action
        return attr

    @property
    def callback_event(self):
        """ Returns the name of the entity. """
        return self._callback_event

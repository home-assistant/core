"""
APNS Notification platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.apns/
"""
import logging
import os
import voluptuous as vol

from homeassistant.helpers.event import track_state_change
from homeassistant.config import load_yaml_config_file
from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_DATA, BaseNotificationService)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import template as template_helper

DOMAIN = "apns"
APNS_DEVICES = "apns.yaml"
DEVICE_TRACKER_DOMAIN = "device_tracker"
SERVICE_REGISTER = "apns_register"

ATTR_PUSH_ID = "push_id"
ATTR_NAME = "name"

REGISTER_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_PUSH_ID): cv.string,
    vol.Optional(ATTR_NAME, default=None): cv.string,
})

REQUIREMENTS = ["apns2==0.1.1"]


def get_service(hass, config):
    """Return push service."""
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    name = config.get("name")
    if name is None:
        logging.error("Name must be specified.")
        return None

    cert_file = config.get('cert_file')
    if cert_file is None:
        logging.error("Certificate must be specified.")
        return None

    topic = config.get('topic')
    if topic is None:
        logging.error("Topic must be specified.")
        return None

    sandbox = bool(config.get('sandbox', False))

    service = ApnsNotificationService(hass, name, topic, sandbox, cert_file)
    hass.services.register(DOMAIN,
                           name,
                           service.register,
                           descriptions.get(SERVICE_REGISTER),
                           schema=REGISTER_SERVICE_SCHEMA)
    return service


class ApnsDevice(object):
    """
    Apns Device class.

    Stores information about a device that is
    registered for push notifications.
    """

    def __init__(self, push_id, name, tracking_device_id=None, disabled=False):
        """Initialize Apns Device."""
        self.device_push_id = push_id
        self.device_name = name
        self.tracking_id = tracking_device_id
        self.device_disabled = disabled

    @property
    def push_id(self):
        """The apns id for the device."""
        return self.device_push_id

    @property
    def name(self):
        """The friendly name for the device."""
        return self.device_name

    @property
    def tracking_device_id(self):
        """
        Device Id.

        The id of a device that is tracked by the device
        tracking component.
        """
        return self.tracking_id

    @property
    def full_tracking_device_id(self):
        """
        Fully qualified device id.

        The full id of a device that is tracked by the device
        tracking component.
        """
        return DEVICE_TRACKER_DOMAIN + '.' + self.tracking_id

    @property
    def disabled(self):
        """Should receive notifications."""
        return self.device_disabled

    def disable(self):
        """Disable the device from recieving notifications."""
        self.device_disabled = True

    def __eq__(self, other):
        """Return the comparision."""
        if isinstance(other, self.__class__):
            return self.push_id == other.push_id and self.name == other.name
        return NotImplemented

    def __ne__(self, other):
        """Return the comparision."""
        return not self.__eq__(other)


class ApnsNotificationService(BaseNotificationService):
    """Implement the notification service for the APNS service."""

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass, app_name, topic, sandbox, cert_file):
        """Initialize APNS application."""
        self.hass = hass
        self.app_name = app_name
        self.sandbox = sandbox
        self.certificate = cert_file
        self.yaml_path = hass.config.path(app_name + '_' + APNS_DEVICES)
        self.devices = {}
        self.device_states = {}
        self.topic = topic
        if os.path.isfile(self.yaml_path):
            self.devices = {
                str(key): ApnsDevice(
                    str(key),
                    value.get('name'),
                    value.get('tracking_device_id'),
                    value.get('disabled', False)
                )
                for (key, value) in
                load_yaml_config_file(self.yaml_path).items()
            }

        tracking_ids = [
            device.full_tracking_device_id
            for (key, device) in self.devices.items()
            if device.tracking_device_id is not None
        ]
        track_state_change(
            hass,
            tracking_ids,
            self.device_state_changed_listener)

    def device_state_changed_listener(self, entity_id, from_s, to_s):
        """
        Listener for sate change.

        Track device state change if a device
        has a tracking id specified.
        """
        self.device_states[entity_id] = str(to_s.state)
        return

    @staticmethod
    def write_device(out, device):
        """Write a single device to file."""
        attributes = []
        if device.name is not None:
            attributes.append(
                'name: {}'.format(device.name))
        if device.tracking_device_id is not None:
            attributes.append(
                'tracking_device_id: {}'.format(device.tracking_device_id))
        if device.disabled:
            attributes.append('disabled: True')

        out.write(device.push_id)
        out.write(": {")
        if len(attributes) > 0:
            separator = ", "
            out.write(separator.join(attributes))

        out.write("}\n")

    def write_devices(self):
        """Write all known devices to file."""
        with open(self.yaml_path, 'w+') as out:
            for _, device in self.devices.items():
                ApnsNotificationService.write_device(out, device)

    def register(self, call):
        """Register a device to receive push messages."""
        push_id = call.data.get(ATTR_PUSH_ID)
        if push_id is None:
            return False

        device_name = call.data.get(ATTR_NAME)
        current_device = self.devices.get(push_id)
        current_tracking_id = None if current_device is None \
            else current_device.tracking_device_id

        device = ApnsDevice(
            push_id,
            device_name,
            current_tracking_id)

        if current_device is None:
            self.devices[push_id] = device
            with open(self.yaml_path, 'a') as out:
                self.write_device(out, device)
            return True

        if device != current_device:
            self.devices[push_id] = device
            self.write_devices()

        return True

    def send_message(self, message=None, **kwargs):
        """Send push message to registered devices."""
        from apns2.client import APNsClient
        from apns2.payload import Payload
        from apns2.errors import Unregistered

        apns = APNsClient(
            self.certificate,
            use_sandbox=self.sandbox,
            use_alternative_port=False)

        device_state = kwargs.get(ATTR_TARGET)
        message_data = kwargs.get(ATTR_DATA)

        if message_data is None:
            message_data = {}

        if isinstance(message, str):
            rendered_message = message
        elif isinstance(message, template_helper.Template):
            rendered_message = message.render()
        else:
            rendered_message = ""

        payload = Payload(
            alert=rendered_message,
            badge=message_data.get("badge"),
            sound=message_data.get("sound"),
            category=message_data.get("category"),
            custom=message_data.get("custom", {}),
            content_available=message_data.get("content_available", False))

        device_update = False

        for push_id, device in self.devices.items():
            if not device.disabled:
                state = None
                if device.tracking_device_id is not None:
                    state = self.device_states.get(
                        device.full_tracking_device_id)

                if device_state is None or state == str(device_state):
                    try:
                        apns.send_notification(
                            push_id,
                            payload,
                            topic=self.topic)
                    except Unregistered:
                        logging.error(
                            "Device %s has unregistered.",
                            push_id)
                        device_update = True
                        device.disable()

        if device_update:
            self.write_devices()

        return True

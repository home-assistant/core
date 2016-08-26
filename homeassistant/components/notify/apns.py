"""
APNS Notification platform.

The APNS platform uses the Apple Push Notification service (APNS) to deliver
notifications from Home Assistant.

To use the APNS service you will need an apple developer account
and you will need to create an App to receive push notifications.
For more information see the apple developer documentation.

Sample Configuration:

    notify:
      platform: apns
      name: doorbell_app
      sandbox: true
      cert_file: doorbell_app.pem

Configuration Variables:

    name:
        The name of the app.
    sandbox:
        If true notifications will be sent to the sandbox (test) notification
        service.
    cert_file:
        The certificate to use to authenticate with the APNS service.

Usage:

    The APNS platform will register two services, notify/[app_name] and
    apns/[app_name].

    apns/app_name:
        This service will register device id's with home assistant. In order to
        receive a notification a device must be registered. The app on the
        device can use this service to send its id during startup, the id will
        be stored in the [app_name]_apns.yaml.

        See didRegisterForRemoteNotificationsWithDeviceToken in the apple
        developer documentation for more information.


    notify/app_name
        This service will send messages to a registered device. The following
        parameters can be used:

        message:
            The message to send

        target:
            The desired state of the device, only devices that match the state
            will receive messages. To enable state tracking a registered
            device must have a device_tracking_id added to the
            [app_name]_apns.yaml file. If this id matches a device in
            known_devices.yaml its state will be tracked.

        data:
            badge:
                The number to display as the badge of the app ic
            sound:
                The name of a sound file in the app bundle or in the
                Library/Sounds folder.
            category:
                Provide this key with a string value that represents the
                identifier property of the UIMutableUserNotificationCategory
            content_available:
                Provide this key with a value of 1 to indicate that new
                content is available.
"""
import logging
import os
import voluptuous as vol

from homeassistant.helpers.event import track_state_change
from homeassistant.config import load_yaml_config_file
from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_DATA, BaseNotificationService)
import homeassistant.helpers.config_validation as cv

DOMAIN = "apns"
APNS_DEVICES = "apns.yaml"
DEVICE_TRACKER_DOMAIN = "device_tracker"
SERVICE_REGISTER = "register"

ATTR_PUSH_ID = "push_id"
ATTR_NAME = "name"

REGISTER_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_PUSH_ID): cv.template,
    vol.Optional(ATTR_NAME, default=None): cv.string,
})

REQUIREMENTS = ["apns3==1.0.0"]


def get_service(hass, config):
    """Return push service."""
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'apns_services.yaml'))

    name = config.get("name")
    if name is None:
        logging.error("Name must be specified.")
        return None

    cert_file = config.get('cert_file')
    if cert_file is None:
        logging.error("Certificate must be specified.")
        return None

    sandbox = bool(config.get('sandbox', False))

    service = ApnsNotificationService(hass, name, sandbox, cert_file)
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

    def __init__(self, push_id, name, tracking_device_id=None):
        """Initialize Apns Device."""
        self.device_push_id = push_id
        self.device_name = name
        self.tracking_id = tracking_device_id

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

    def __eq__(self, other):
        """Return the comparision."""
        if isinstance(other, self.__class__):
            return self.push_id == other.push_id and self.name == other.name
        return NotImplemented

    def __ne__(self, other):
        """Return the comparision."""
        return not self.__eq__(other)


class ApnsNotificationService(BaseNotificationService):
    """Implement the notification service for the AWS SNS service."""

    def __init__(self, hass, app_name, sandbox, cert_file):
        """Initialize APNS application."""
        self.hass = hass
        self.app_name = app_name
        self.sandbox = sandbox
        self.certificate = cert_file
        self.yaml_path = hass.config.path(app_name + '_' + APNS_DEVICES)
        self.devices = {}
        self.device_states = {}
        if os.path.isfile(self.yaml_path):
            self.devices = {
                str(key): ApnsDevice(
                    str(key),
                    value.get('name'),
                    value.get('tracking_device_id')
                )
                for (key, value) in
                load_yaml_config_file(self.yaml_path).items()
            }

        def state_changed_listener(entity_id, from_s, to_s):
            """
            Listener for sate change.

            Track device state change if a device
            has a tracking id specified.
            """
            self.device_states[entity_id] = str(to_s.state)
            return

        tracking_ids = [
            device.full_tracking_device_id
            for (key, device) in self.devices.items()
            if device.tracking_device_id is not None
        ]
        track_state_change(hass, tracking_ids, state_changed_listener)

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
            return

        if device != current_device:
            self.devices[push_id] = device
            self.write_devices()

        return True

    def send_message(self, message="", **kwargs):
        """Send push message to registered devices."""
        from apns3 import APNs, Payload

        apns = APNs(
            use_sandbox=self.sandbox,
            cert_file=self.certificate,
            key_file=self.certificate)

        device_state = kwargs.get(ATTR_TARGET)
        message_data = kwargs.get(ATTR_DATA)

        if message_data is None:
            message_data = {}

        payload = Payload(
            message,
            message_data.get("badge"),
            message_data.get("sound"),
            message_data.get("category"),
            message_data.get("custom", {}),
            message_data.get("content_available", False))

        for push_id, device in self.devices.items():
            if device_state is None:
                apns.gateway_server.send_notification(push_id, payload)
            elif device.tracking_device_id is not None:
                state = self.device_states.get(device.full_tracking_device_id)
                if state == str(device_state):
                    apns.gateway_server.send_notification(push_id, payload)

        return True

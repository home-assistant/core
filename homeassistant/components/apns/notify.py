"""APNS Notification platform."""
import logging

from apns2.client import APNsClient
from apns2.errors import Unregistered
from apns2.payload import Payload
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import ATTR_NAME, CONF_NAME, CONF_PLATFORM
from homeassistant.helpers import template as template_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_state_change

from .const import DOMAIN

APNS_DEVICES = "apns.yaml"
CONF_CERTFILE = "cert_file"
CONF_TOPIC = "topic"
CONF_SANDBOX = "sandbox"

ATTR_PUSH_ID = "push_id"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "apns",
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_CERTFILE): cv.isfile,
        vol.Required(CONF_TOPIC): cv.string,
        vol.Optional(CONF_SANDBOX, default=False): cv.boolean,
    }
)

REGISTER_SERVICE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_PUSH_ID): cv.string, vol.Optional(ATTR_NAME): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Return push service."""
    name = config[CONF_NAME]
    cert_file = config[CONF_CERTFILE]
    topic = config[CONF_TOPIC]
    sandbox = config[CONF_SANDBOX]

    service = ApnsNotificationService(hass, name, topic, sandbox, cert_file)
    hass.services.register(
        DOMAIN, f"apns_{name}", service.register, schema=REGISTER_SERVICE_SCHEMA
    )
    return service


class ApnsDevice:
    """
    The APNS Device class.

    Stores information about a device that is registered for push
    notifications.
    """

    def __init__(self, push_id, name, tracking_device_id=None, disabled=False):
        """Initialize APNS Device."""
        self.device_push_id = push_id
        self.device_name = name
        self.tracking_id = tracking_device_id
        self.device_disabled = disabled

    @property
    def push_id(self):
        """Return the  APNS id for the device."""
        return self.device_push_id

    @property
    def name(self):
        """Return the friendly name for the device."""
        return self.device_name

    @property
    def tracking_device_id(self):
        """
        Return the device Id.

        The id of a device that is tracked by the device
        tracking component.
        """
        return self.tracking_id

    @property
    def full_tracking_device_id(self):
        """
        Return the fully qualified device id.

        The full id of a device that is tracked by the device
        tracking component.
        """
        return f"{DEVICE_TRACKER_DOMAIN}.{self.tracking_id}"

    @property
    def disabled(self):
        """Return the state of the service."""
        return self.device_disabled

    def disable(self):
        """Disable the device from receiving notifications."""
        self.device_disabled = True

    def __eq__(self, other):
        """Return the comparison."""
        if isinstance(other, self.__class__):
            return self.push_id == other.push_id and self.name == other.name
        return NotImplemented

    def __ne__(self, other):
        """Return the comparison."""
        return not self.__eq__(other)


def _write_device(out, device):
    """Write a single device to file."""
    attributes = []
    if device.name is not None:
        attributes.append(f"name: {device.name}")
    if device.tracking_device_id is not None:
        attributes.append(f"tracking_device_id: {device.tracking_device_id}")
    if device.disabled:
        attributes.append("disabled: True")

    out.write(device.push_id)
    out.write(": {")
    if attributes:
        separator = ", "
        out.write(separator.join(attributes))

    out.write("}\n")


class ApnsNotificationService(BaseNotificationService):
    """Implement the notification service for the APNS service."""

    def __init__(self, hass, app_name, topic, sandbox, cert_file):
        """Initialize APNS application."""
        self.hass = hass
        self.app_name = app_name
        self.sandbox = sandbox
        self.certificate = cert_file
        self.yaml_path = hass.config.path(f"{app_name}_{APNS_DEVICES}")
        self.devices = {}
        self.device_states = {}
        self.topic = topic

        try:
            self.devices = {
                str(key): ApnsDevice(
                    str(key),
                    value.get("name"),
                    value.get("tracking_device_id"),
                    value.get("disabled", False),
                )
                for (key, value) in load_yaml_config_file(self.yaml_path).items()
            }
        except FileNotFoundError:
            pass

        tracking_ids = [
            device.full_tracking_device_id
            for (key, device) in self.devices.items()
            if device.tracking_device_id is not None
        ]
        track_state_change(hass, tracking_ids, self.device_state_changed_listener)

    def device_state_changed_listener(self, entity_id, from_s, to_s):
        """
        Listen for state change.

        Track device state change if a device has a tracking id specified.
        """
        self.device_states[entity_id] = str(to_s.state)

    def write_devices(self):
        """Write all known devices to file."""
        with open(self.yaml_path, "w+") as out:
            for device in self.devices.values():
                _write_device(out, device)

    def register(self, call):
        """Register a device to receive push messages."""
        push_id = call.data.get(ATTR_PUSH_ID)

        device_name = call.data.get(ATTR_NAME)
        current_device = self.devices.get(push_id)
        current_tracking_id = (
            None if current_device is None else current_device.tracking_device_id
        )

        device = ApnsDevice(push_id, device_name, current_tracking_id)

        if current_device is None:
            self.devices[push_id] = device
            with open(self.yaml_path, "a") as out:
                _write_device(out, device)
            return True

        if device != current_device:
            self.devices[push_id] = device
            self.write_devices()

        return True

    def send_message(self, message=None, **kwargs):
        """Send push message to registered devices."""

        apns = APNsClient(
            self.certificate, use_sandbox=self.sandbox, use_alternative_port=False
        )

        device_state = kwargs.get(ATTR_TARGET)
        message_data = kwargs.get(ATTR_DATA)

        if message_data is None:
            message_data = {}

        if isinstance(message, str):
            rendered_message = message
        elif isinstance(message, template_helper.Template):
            rendered_message = message.render(parse_result=False)
        else:
            rendered_message = ""

        payload = Payload(
            alert=rendered_message,
            badge=message_data.get("badge"),
            sound=message_data.get("sound"),
            category=message_data.get("category"),
            custom=message_data.get("custom", {}),
            content_available=message_data.get("content_available", False),
        )

        device_update = False

        for push_id, device in self.devices.items():
            if not device.disabled:
                state = None
                if device.tracking_device_id is not None:
                    state = self.device_states.get(device.full_tracking_device_id)

                if device_state is None or state == str(device_state):
                    try:
                        apns.send_notification(push_id, payload, topic=self.topic)
                    except Unregistered:
                        logging.error("Device %s has unregistered", push_id)
                        device_update = True
                        device.disable()

        if device_update:
            self.write_devices()

        return True

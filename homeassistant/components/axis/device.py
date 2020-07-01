"""Axis network device abstraction."""

import asyncio

import async_timeout
import axis
from axis.configuration import Configuration
from axis.errors import Unauthorized
from axis.event_stream import OPERATION_INITIALIZED
from axis.mqtt import mqtt_json_to_event
from axis.streammanager import SIGNAL_PLAYING, STATE_STOPPED

from homeassistant.components import mqtt
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.mqtt.models import Message
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TRIGGER_TIME,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_when_setup

from .const import (
    ATTR_MANUFACTURER,
    CONF_CAMERA,
    CONF_EVENTS,
    CONF_MODEL,
    CONF_STREAM_PROFILE,
    DEFAULT_EVENTS,
    DEFAULT_STREAM_PROFILE,
    DEFAULT_TRIGGER_TIME,
    DOMAIN as AXIS_DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .errors import AuthenticationRequired, CannotConnect


class AxisNetworkDevice:
    """Manages a Axis device."""

    def __init__(self, hass, config_entry):
        """Initialize the device."""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True

        self.api = None
        self.fw_version = None
        self.product_type = None

        self.listeners = []

    @property
    def host(self):
        """Return the host of this device."""
        return self.config_entry.data[CONF_HOST]

    @property
    def model(self):
        """Return the model of this device."""
        return self.config_entry.data[CONF_MODEL]

    @property
    def name(self):
        """Return the name of this device."""
        return self.config_entry.data[CONF_NAME]

    @property
    def serial(self):
        """Return the serial number of this device."""
        return self.config_entry.unique_id

    @property
    def option_camera(self):
        """Config entry option defining if camera should be used."""
        supported_formats = self.api.vapix.params.image_format
        return self.config_entry.options.get(CONF_CAMERA, bool(supported_formats))

    @property
    def option_events(self):
        """Config entry option defining if platforms based on events should be created."""
        return self.config_entry.options.get(CONF_EVENTS, DEFAULT_EVENTS)

    @property
    def option_stream_profile(self):
        """Config entry option defining what stream profile camera platform should use."""
        return self.config_entry.options.get(
            CONF_STREAM_PROFILE, DEFAULT_STREAM_PROFILE
        )

    @property
    def option_trigger_time(self):
        """Config entry option defining minimum number of seconds to keep trigger high."""
        return self.config_entry.options.get(CONF_TRIGGER_TIME, DEFAULT_TRIGGER_TIME)

    @property
    def signal_reachable(self):
        """Device specific event to signal a change in connection status."""
        return f"axis_reachable_{self.serial}"

    @property
    def signal_new_event(self):
        """Device specific event to signal new device event available."""
        return f"axis_new_event_{self.serial}"

    @property
    def signal_new_address(self):
        """Device specific event to signal a change in device address."""
        return f"axis_new_address_{self.serial}"

    @callback
    def async_connection_status_callback(self, status):
        """Handle signals of device connection status.

        This is called on every RTSP keep-alive message.
        Only signal state change if state change is true.
        """

        if self.available != (status == SIGNAL_PLAYING):
            self.available = not self.available
            async_dispatcher_send(self.hass, self.signal_reachable, True)

    @callback
    def async_event_callback(self, action, event_id):
        """Call to configure events when initialized on event stream."""
        if action == OPERATION_INITIALIZED:
            async_dispatcher_send(self.hass, self.signal_new_event, event_id)

    @staticmethod
    async def async_new_address_callback(hass, entry):
        """Handle signals of device getting new address.

        Called when config entry is updated.
        This is a static method because a class method (bound method),
        can not be used with weak references.
        """
        device = hass.data[AXIS_DOMAIN][entry.unique_id]
        device.api.config.host = device.host
        async_dispatcher_send(hass, device.signal_new_address)

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.serial)},
            identifiers={(AXIS_DOMAIN, self.serial)},
            manufacturer=ATTR_MANUFACTURER,
            model=f"{self.model} {self.product_type}",
            name=self.name,
            sw_version=self.fw_version,
        )

    async def use_mqtt(self, hass: HomeAssistant, component: str) -> None:
        """Set up to use MQTT."""
        try:
            status = await hass.async_add_executor_job(
                self.api.vapix.mqtt.get_client_status
            )
        except Unauthorized:
            # This means the user has too low privileges
            status = {}

        if status.get("data", {}).get("status", {}).get("state") == "active":
            self.listeners.append(
                await mqtt.async_subscribe(hass, f"{self.serial}/#", self.mqtt_message)
            )

    @callback
    def mqtt_message(self, message: Message) -> None:
        """Receive Axis MQTT message."""
        self.disconnect_from_stream()

        event = mqtt_json_to_event(message.payload)
        self.api.event.process_event(event)

    async def async_setup(self):
        """Set up the device."""
        try:
            self.api = await get_device(
                self.hass,
                host=self.config_entry.data[CONF_HOST],
                port=self.config_entry.data[CONF_PORT],
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
            )

        except CannotConnect:
            raise ConfigEntryNotReady

        except Exception:  # pylint: disable=broad-except
            LOGGER.error("Unknown error connecting with Axis device on %s", self.host)
            return False

        self.fw_version = self.api.vapix.firmware_version
        self.product_type = self.api.vapix.product_type

        async def start_platforms():
            await asyncio.gather(
                *[
                    self.hass.config_entries.async_forward_entry_setup(
                        self.config_entry, platform
                    )
                    for platform in PLATFORMS
                ]
            )
            if self.option_events:
                self.api.stream.connection_status_callback.append(
                    self.async_connection_status_callback
                )
                self.api.enable_events(event_callback=self.async_event_callback)
                self.api.stream.start()

                if self.api.vapix.mqtt:
                    async_when_setup(self.hass, MQTT_DOMAIN, self.use_mqtt)

        self.hass.async_create_task(start_platforms())

        self.config_entry.add_update_listener(self.async_new_address_callback)

        return True

    @callback
    def disconnect_from_stream(self):
        """Stop stream."""
        if self.api.stream.state != STATE_STOPPED:
            self.api.stream.connection_status_callback.remove(
                self.async_connection_status_callback
            )
            self.api.stream.stop()

    @callback
    def shutdown(self, event):
        """Stop the event stream."""
        self.disconnect_from_stream()

    async def async_reset(self):
        """Reset this device to default state."""
        self.disconnect_from_stream()

        unload_ok = all(
            await asyncio.gather(
                *[
                    self.hass.config_entries.async_forward_entry_unload(
                        self.config_entry, platform
                    )
                    for platform in PLATFORMS
                ]
            )
        )
        if not unload_ok:
            return False

        for unsubscribe_listener in self.listeners:
            unsubscribe_listener()

        return True


async def get_device(hass, host, port, username, password):
    """Create a Axis device."""

    device = axis.AxisDevice(
        Configuration(host, port=port, username=username, password=password)
    )

    try:
        with async_timeout.timeout(15):
            await hass.async_add_executor_job(device.vapix.initialize)

        return device

    except axis.Unauthorized:
        LOGGER.warning("Connected to device at %s but not registered.", host)
        raise AuthenticationRequired

    except (asyncio.TimeoutError, axis.RequestError):
        LOGGER.error("Error connecting to the Axis device at %s", host)
        raise CannotConnect

    except axis.AxisException:
        LOGGER.exception("Unknown Axis communication error occurred")
        raise AuthenticationRequired

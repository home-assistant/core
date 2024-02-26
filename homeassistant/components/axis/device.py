"""Axis network device abstraction."""

from asyncio import timeout
from types import MappingProxyType
from typing import Any

import axis
from axis.configuration import Configuration
from axis.errors import Unauthorized
from axis.stream_manager import Signal, State
from axis.vapix.interfaces.mqtt import mqtt_json_to_event

from homeassistant.components import mqtt
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TRIGGER_TIME,
    CONF_USERNAME,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.setup import async_when_setup

from .const import (
    ATTR_MANUFACTURER,
    CONF_EVENTS,
    CONF_STREAM_PROFILE,
    CONF_VIDEO_SOURCE,
    DEFAULT_EVENTS,
    DEFAULT_STREAM_PROFILE,
    DEFAULT_TRIGGER_TIME,
    DEFAULT_VIDEO_SOURCE,
    DOMAIN as AXIS_DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .errors import AuthenticationRequired, CannotConnect


class AxisNetworkDevice:
    """Manages a Axis device."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: axis.AxisDevice
    ) -> None:
        """Initialize the device."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api

        self.available = True
        self.fw_version = api.vapix.firmware_version
        self.product_type = api.vapix.product_type

        self.additional_diagnostics: dict[str, Any] = {}

    @property
    def host(self) -> str:
        """Return the host address of this device."""
        host: str = self.config_entry.data[CONF_HOST]
        return host

    @property
    def port(self) -> int:
        """Return the HTTP port of this device."""
        port: int = self.config_entry.data[CONF_PORT]
        return port

    @property
    def username(self) -> str:
        """Return the username of this device."""
        username: str = self.config_entry.data[CONF_USERNAME]
        return username

    @property
    def password(self) -> str:
        """Return the password of this device."""
        password: str = self.config_entry.data[CONF_PASSWORD]
        return password

    @property
    def model(self) -> str:
        """Return the model of this device."""
        model: str = self.config_entry.data[CONF_MODEL]
        return model

    @property
    def name(self) -> str:
        """Return the name of this device."""
        name: str = self.config_entry.data[CONF_NAME]
        return name

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID (serial number) of this device."""
        return self.config_entry.unique_id

    # Options

    @property
    def option_events(self) -> bool:
        """Config entry option defining if platforms based on events should be created."""
        return self.config_entry.options.get(CONF_EVENTS, DEFAULT_EVENTS)

    @property
    def option_stream_profile(self) -> str:
        """Config entry option defining what stream profile camera platform should use."""
        return self.config_entry.options.get(
            CONF_STREAM_PROFILE, DEFAULT_STREAM_PROFILE
        )

    @property
    def option_trigger_time(self) -> int:
        """Config entry option defining minimum number of seconds to keep trigger high."""
        return self.config_entry.options.get(CONF_TRIGGER_TIME, DEFAULT_TRIGGER_TIME)

    @property
    def option_video_source(self) -> str:
        """Config entry option defining what video source camera platform should use."""
        return self.config_entry.options.get(CONF_VIDEO_SOURCE, DEFAULT_VIDEO_SOURCE)

    # Signals

    @property
    def signal_reachable(self) -> str:
        """Device specific event to signal a change in connection status."""
        return f"axis_reachable_{self.unique_id}"

    @property
    def signal_new_address(self) -> str:
        """Device specific event to signal a change in device address."""
        return f"axis_new_address_{self.unique_id}"

    # Callbacks

    @callback
    def async_connection_status_callback(self, status: Signal) -> None:
        """Handle signals of device connection status.

        This is called on every RTSP keep-alive message.
        Only signal state change if state change is true.
        """

        if self.available != (status == Signal.PLAYING):
            self.available = not self.available
            async_dispatcher_send(self.hass, self.signal_reachable)

    @staticmethod
    async def async_new_address_callback(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle signals of device getting new address.

        Called when config entry is updated.
        This is a static method because a class method (bound method),
        cannot be used with weak references.
        """
        device: AxisNetworkDevice = hass.data[AXIS_DOMAIN][entry.entry_id]
        device.api.config.host = device.host
        async_dispatcher_send(hass, device.signal_new_address)

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            configuration_url=self.api.config.url,
            connections={(CONNECTION_NETWORK_MAC, self.unique_id)},  # type: ignore[arg-type]
            identifiers={(AXIS_DOMAIN, self.unique_id)},  # type: ignore[arg-type]
            manufacturer=ATTR_MANUFACTURER,
            model=f"{self.model} {self.product_type}",
            name=self.name,
            sw_version=self.fw_version,
        )

    async def async_use_mqtt(self, hass: HomeAssistant, component: str) -> None:
        """Set up to use MQTT."""
        try:
            status = await self.api.vapix.mqtt.get_client_status()
        except Unauthorized:
            # This means the user has too low privileges
            status = {}

        if status.get("data", {}).get("status", {}).get("state") == "active":
            self.config_entry.async_on_unload(
                await mqtt.async_subscribe(
                    hass, f"{self.api.vapix.serial_number}/#", self.mqtt_message
                )
            )

    @callback
    def mqtt_message(self, message: ReceiveMessage) -> None:
        """Receive Axis MQTT message."""
        self.disconnect_from_stream()

        event = mqtt_json_to_event(message.payload)
        self.api.event.handler(event)

    # Setup and teardown methods

    def async_setup_events(self) -> None:
        """Set up the device events."""

        if self.option_events:
            self.api.stream.connection_status_callback.append(
                self.async_connection_status_callback
            )
            self.api.enable_events()
            self.api.stream.start()

            if self.api.vapix.mqtt:
                async_when_setup(self.hass, MQTT_DOMAIN, self.async_use_mqtt)

    @callback
    def disconnect_from_stream(self) -> None:
        """Stop stream."""
        if self.api.stream.state != State.STOPPED:
            self.api.stream.connection_status_callback.clear()
        self.api.stream.stop()

    async def shutdown(self, event: Event) -> None:
        """Stop the event stream."""
        self.disconnect_from_stream()

    async def async_reset(self) -> bool:
        """Reset this device to default state."""
        self.disconnect_from_stream()

        return await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )


async def get_axis_device(
    hass: HomeAssistant,
    config: MappingProxyType[str, Any],
) -> axis.AxisDevice:
    """Create a Axis device."""
    session = get_async_client(hass, verify_ssl=False)

    device = axis.AxisDevice(
        Configuration(
            session,
            config[CONF_HOST],
            port=config[CONF_PORT],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
        )
    )

    try:
        async with timeout(30):
            await device.vapix.initialize()

        return device

    except axis.Unauthorized as err:
        LOGGER.warning(
            "Connected to device at %s but not registered", config[CONF_HOST]
        )
        raise AuthenticationRequired from err

    except (TimeoutError, axis.RequestError) as err:
        LOGGER.error("Error connecting to the Axis device at %s", config[CONF_HOST])
        raise CannotConnect from err

    except axis.AxisException as err:
        LOGGER.exception("Unknown Axis communication error occurred")
        raise AuthenticationRequired from err

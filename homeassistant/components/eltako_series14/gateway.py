"""Representation of an Eltako Series 14 gateway."""

from collections.abc import Callable
import logging
from typing import Any

from eltakobus.eep import WrongOrgError
from eltakobus.message import (
    EltakoPoll,
    EltakoWrapped1BS,
    EltakoWrapped4BS,
    EltakoWrappedRPS,
    ESP2Message,
    Regular1BSMessage,
    Regular4BSMessage,
    RPSMessage,
)
from eltakobus.serial import RS485SerialInterfaceV2
from eltakobus.util import AddressExpression

from homeassistant.core import HomeAssistant

from .device import GatewayModelDefinition

_LOGGER = logging.getLogger(__name__)

type MessageCallback = Callable[[ESP2Message], None]
type GwConnectionCallback = Callable[[bool], None]


class EltakoGateway:
    """Representation of an Eltako gateway.

    The gateway is responsible for receiving the Eltako frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        device_model: GatewayModelDefinition,
        serial_port: str,
        auto_reconnect_enabled: bool,
        message_delay: float,
        fast_status_change: bool,
    ) -> None:
        """Initialize the Eltako gateway."""
        _LOGGER.debug("Initialize a gateway device")

        self.hass = hass
        self._device_model = device_model
        self._serial_port = serial_port
        self._auto_reconnect_enabled = auto_reconnect_enabled
        self._message_delay = message_delay
        self._fast_status_change = fast_status_change

        self._bus: RS485SerialInterfaceV2 | None = None
        self._address_subscriptions: dict[Any, list[MessageCallback]] = {}
        self._general_subscriptions: list[Callable[[], None]] = []
        self._connection_state_subscriptons: list[GwConnectionCallback] = []

    def _init_bus(self) -> None:
        """Initialize the serial bus."""
        self._bus = RS485SerialInterfaceV2(
            self._serial_port,
            baud_rate=self._device_model.baud_rate,
            callback=self._callback_receive_message_from_serial_bus,
            delay_message=self._message_delay,
            auto_reconnect=self._auto_reconnect_enabled,
        )
        self._bus.set_status_changed_handler(self._fire_connection_state_changed_event)
        self._bus.start()
        _LOGGER.debug("%s was started", self._serial_port)

    async def async_setup(self) -> None:
        """Initialize the serial bus."""
        await self.hass.async_add_executor_job(self._init_bus)

    def _unload(self) -> None:
        """Unload the serial bus."""
        if self._bus:
            self._bus.stop()
            self._bus.join()
            _LOGGER.debug("%s was stopped", self._serial_port)

    async def async_unload(self) -> None:
        """Unload the serial bus."""
        await self.hass.async_add_executor_job(self._unload)

    def _reconnect(self) -> None:
        """Reconnecting the gateway."""
        self._unload()
        self._init_bus()

    async def async_reconnect(self) -> None:
        """Reconnecting the gateway."""
        await self.hass.async_add_executor_job(self._reconnect)

    def subscribe_address(
        self, address: AddressExpression, callback: MessageCallback
    ) -> Callable[[], None]:
        """Register a callback for a specific address."""
        self._address_subscriptions.setdefault(address[0], []).append(callback)
        # Return an "unsubscribe" function
        return lambda: self._address_subscriptions[address[0]].remove(callback)

    def subscribe_message_received(
        self, callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback for any message."""
        self._general_subscriptions.append(callback)
        # Return an "unsubscribe" function
        return lambda: self._general_subscriptions.remove(callback)

    def susbcribe_connection_state(
        self, callback: GwConnectionCallback
    ) -> Callable[[], None]:
        """Register a callback for the gateway connection state."""
        self._connection_state_subscriptons.append(callback)
        if self._bus:
            callback(self._bus.is_active())
        # Return an "unsubscribe" function
        return lambda: self._connection_state_subscriptons.remove(callback)

    def _fire_connection_state_changed_event(self, status: bool) -> None:
        for callback in self._connection_state_subscriptons:
            callback(status)

    async def async_send_message_to_serial_bus(self, msg: ESP2Message) -> None:
        """Send a message to the serial bus."""
        if self._bus and self._bus.is_active():
            _LOGGER.debug("Send message: %s (%s)", msg, msg.serialize().hex())
            await self._bus.send(msg)
        else:
            _LOGGER.warning("Serial port %s is not available", self._serial_port)

    def _callback_receive_message_from_serial_bus(
        self, msg: ESP2Message | None = None
    ) -> None:
        """Handle incoming messages."""
        if not msg or isinstance(msg, EltakoPoll):
            return

        _LOGGER.debug("[%s] Received message: %s", self._serial_port, msg)
        self.hass.loop.call_soon_threadsafe(self._handle_incoming_message, msg)

    def _handle_incoming_message(self, msg: ESP2Message) -> None:
        """Process messages on the main event loop."""
        for general_callback in self._general_subscriptions:
            general_callback()

        msg_classes = (
            EltakoWrappedRPS,
            EltakoWrapped1BS,
            EltakoWrapped4BS,
            RPSMessage,
            Regular1BSMessage,
            Regular4BSMessage,
        )

        if isinstance(msg, msg_classes) and msg.address in self._address_subscriptions:
            for address_callback in self._address_subscriptions[msg.address]:
                try:
                    address_callback(msg)
                except WrongOrgError:
                    _LOGGER.warning("Could not decode message: %s", msg)

    @property
    def model(self) -> str:
        """Return the model of the gateway."""
        return self._device_model.name

    @property
    def message_delay(self) -> float:
        """Return the message delay of single telegrams to be sent."""
        return self._message_delay

    @property
    def fast_status_change(self) -> bool:
        """Return whether the gateway is set up to change the entities status directly."""
        return self._fast_status_change

    @property
    def auto_reconnect_enabled(self) -> bool:
        """Return if auto connected is enabled."""
        return self._auto_reconnect_enabled

"""Qbus Hub."""

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import PLATFORMS
from .entity import QbusEntity
from .qbus_entry import QbusEntry
from .qbus_mqtt import QbusMqttConfig, QbusMqttControllerState, QbusMqttDevice

_LOGGER = logging.getLogger(__name__)


class QbusHub:
    """Qbus Hub."""

    _WAIT_TIME = 3

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Qbus Hub."""

        self._hass = hass
        self._entry = QbusEntry(hass, entry)

        self._qbus_config: QbusMqttConfig | None = None
        self._platform_register: dict[
            str, tuple[type[QbusEntity], AddEntitiesCallback]
        ] = {}
        self._registered_entity_ids: list[str] = []

    async def async_setup_entry(self) -> None:
        """Set up Qbus Hub for a config entry."""
        _LOGGER.debug("Setting up entry")

        self._entry.state_queue.start()

        await self._hass.config_entries.async_forward_entry_setups(
            self._entry.config_entry, PLATFORMS
        )

        self._entry.config_entry.async_on_unload(
            self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        )

        # Subscribe to option updates
        self._entry.config_entry.async_on_unload(
            self._entry.config_entry.add_update_listener(self._options_update_listener)
        )

        _LOGGER.debug("Subscribing to cloudapp/QBUSMQTTGW/config")
        self._entry.config_entry.async_on_unload(
            await mqtt.async_subscribe(
                self._hass, "cloudapp/QBUSMQTTGW/config", self._config_received
            )
        )

        async_call_later(self._hass, self._WAIT_TIME, self._request_config)

    def shutdown(self, event: Event | None = None) -> None:
        """Shutdown Qbus Hub."""
        _LOGGER.debug("Shutting down hub")

        self._registered_entity_ids = []
        self._entry.state_queue.close()

    def remove(self) -> None:
        """Remove Qbus Hub."""
        _LOGGER.debug("Removing hub")

        self.shutdown()

    def register_platform(
        self,
        qbusType: str,
        entity_class: type[QbusEntity],
        add_entities: AddEntitiesCallback,
    ) -> None:
        """Register the platform so adding entities can be postponed to when the Qbus config is received."""
        _LOGGER.debug("Registering %s", qbusType)

        self._platform_register[qbusType] = (entity_class, add_entities)

    async def _request_config(self, *args, **kwargs) -> None:
        _LOGGER.debug("Requesting Qbus config")
        await mqtt.async_publish(self._hass, "cloudapp/QBUSMQTTGW/getConfig", b"")

    def _request_state(self) -> None:
        @callback
        async def request_state(_) -> None:
            await mqtt.async_publish(
                self._hass,
                "cloudapp/QBUSMQTTGW/getState",
                json.dumps(self._registered_entity_ids),
            )

        if len(self._registered_entity_ids) > 0:
            async_call_later(self._hass, self._WAIT_TIME, request_state)

    @callback
    async def _config_received(self, msg: ReceiveMessage) -> None:
        _LOGGER.debug("Receiving config")

        if len(msg.payload) <= 0:
            return

        self._qbus_config = QbusMqttConfig(json.loads(msg.payload))
        device = self._qbus_config.get_device(self._entry.serial)

        if device is None:
            _LOGGER.warning("Controller with serial %s not found", self._entry.serial)
            return

        _LOGGER.debug("Subscribing to cloudapp/QBUSMQTTGW/%s/state", device.id)
        self._entry.config_entry.async_on_unload(
            await mqtt.async_subscribe(
                self._hass,
                f"cloudapp/QBUSMQTTGW/{device.id}/state",
                self._controller_state_received,
            )
        )

        self._add_entities(device)
        self._request_state()

    @callback
    async def _controller_state_received(self, msg: ReceiveMessage) -> None:
        _LOGGER.debug("Receiving controller state %s", msg.topic)

        if len(msg.payload) <= 0:
            return

        state = QbusMqttControllerState(json.loads(msg.payload))

        if state.properties and state.properties.connectable is False:
            _LOGGER.debug("Activating controller %s", state.id)
            if state.id:
                payload = (
                    '{"id": "'
                    + state.id
                    + '", "type": "action", "action": "activate", "properties": { "authKey": "ubielite" } }'
                )
                await mqtt.async_publish(
                    self._hass, f"cloudapp/QBUSMQTTGW/{state.id}/setState", payload
                )

    def _add_entities(self, device: QbusMqttDevice) -> None:
        """Create the Qbus entities in Home Assistant."""
        _LOGGER.debug(
            "Adding entities for %s registered IDs", len(self._registered_entity_ids)
        )
        items: dict[str, list[QbusEntity]] = {}

        if device.id not in self._registered_entity_ids:
            self._registered_entity_ids.append(device.id)

        # Build list of HA entities based on Qbus configuration
        for output in device.outputs:
            if output.id in self._registered_entity_ids:
                continue

            qbusType = output.type.lower()

            if qbusType not in self._platform_register:
                continue

            self._registered_entity_ids.append(output.id)

            entity_class = self._platform_register[qbusType][0]
            entity = entity_class(output, device, self._entry)
            items.setdefault(qbusType, []).append(entity)

        # Add entities to HA
        _LOGGER.debug("Adding %s entities to HA", len(items))
        for qbusType, entities in items.items():
            add_entities = self._platform_register[qbusType][1]
            add_entities(entities)

    @callback
    async def _homeassistant_started(self, event: Event) -> None:
        @callback
        async def get_config(_) -> None:
            _LOGGER.debug("Requesting Qbus config")
            await mqtt.async_publish(self._hass, "cloudapp/QBUSMQTTGW/getConfig", b"")

        _LOGGER.debug("Home Assistant started")

        if await mqtt.async_wait_for_mqtt_client(self._hass):
            async_call_later(self._hass, self._WAIT_TIME, get_config)

    @callback
    async def _options_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        _LOGGER.debug("Update options %s", entry.entry_id)

        await hass.config_entries.async_reload(entry.entry_id)

"""Qbus Hub."""

import json
import logging

from qbusmqttapi.discovery import QbusDiscovery, QbusMqttControllerState

from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SERIAL, DOMAIN, PLATFORMS
from .entity import QbusEntity
from .qbus_entry import QbusEntry

_LOGGER = logging.getLogger(__name__)


class QbusDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Qbus Data update coordinator."""

    _WAIT_TIME = 3

    def __init__(self, hass: HomeAssistant, configEntry: ConfigEntry) -> None:
        """Initialize Qbus Hub."""
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}")
        self._hass = hass
        self._entry = QbusEntry(hass, configEntry)
        self._config = configEntry
        self._qbus_controller_state = QbusMqttControllerState()
        self._qbus_discovery = QbusDiscovery(DOMAIN)
        self._platform_register: dict[
            str, tuple[type[QbusEntity], AddEntitiesCallback]
        ] = {}
        self._registered_entity_ids: list[str] = []

    def register_platform(
        self,
        qbusType: str,
        entity_class: type[QbusEntity],
        add_entities: AddEntitiesCallback,
    ) -> None:
        """Register the platform so adding entities can be postponed to when the Qbus config is received."""
        _LOGGER.debug("Registering %s", qbusType)
        self._platform_register[qbusType] = (entity_class, add_entities)

    async def async_setup_entry(self) -> None:
        """Set up Qbus Hub for a config entry."""
        _LOGGER.debug("Setting up entry")

        self._entry.state_queue.start()
        await self._hass.config_entries.async_forward_entry_setups(
            self._config, PLATFORMS
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
                self._hass,
                self._qbus_discovery.sub_config_topic,
                self._config_received,
            )
        )

        async_call_later(self._hass, self._WAIT_TIME, self._request_config)

    @callback
    async def _config_received(self, msg: ReceiveMessage) -> None:
        _LOGGER.debug("Receiving config")

        if len(msg.payload) <= 0:
            return

        await self._qbus_discovery.parse_config(msg.topic, msg.payload)
        mydev = self._qbus_discovery.set_device(self._config.data.get(CONF_SERIAL))

        if mydev is None:
            _LOGGER.warning(
                "Controller with serial %s not found",
                self._config.data.get(CONF_SERIAL),
            )
            return

        self._add_entities(mydev)

        await mqtt.async_subscribe(
            self._hass,
            mydev.sub_state_topic,
            self._controller_state_received,
        )

        self._request_controller_state()

    def _add_entities(self, device) -> None:
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
            entity = entity_class(device, output, self._entry)
            items.setdefault(qbusType, []).append(entity)

        # Add entities to HA
        _LOGGER.debug("Adding %s entities to HA", len(items))
        for qbusType, entities in items.items():
            add_entities = self._platform_register[qbusType][1]
            add_entities(entities)

        self._request_state()

    def set_device(self, id: str) -> None:
        """Set device."""
        return self._qbus_discovery.set_device(id)

    def _request_state(self, *args, **kwargs) -> None:
        @callback
        async def request_state(_) -> None:
            await mqtt.async_publish(
                self._hass,
                self._qbus_discovery.get_state_topic,
                json.dumps(self._registered_entity_ids),
            )

        if len(self._registered_entity_ids) > 0:
            async_call_later(self._hass, self._WAIT_TIME, request_state)

    def _request_controller_state(self, *args, **kwargs) -> None:
        @callback
        async def request_controller_state(_) -> None:
            await mqtt.async_publish(
                self._hass,
                self._qbus_discovery.device.req_state_topic,
                self._qbus_discovery.device.state_message,
            )

        async_call_later(self._hass, self._WAIT_TIME, request_controller_state)

    async def _request_config(self, *args, **kwargs) -> None:
        _LOGGER.debug("Requesting Qbus config")
        await mqtt.async_publish(
            self._hass,
            self._qbus_discovery.config_topic,
            "",
        )

    @callback
    async def _controller_state_received(self, msg: ReceiveMessage) -> None:
        _LOGGER.debug("Receiving controller state %s", msg.topic)

        if len(msg.payload) <= 0:
            return

        if await self._qbus_controller_state.parse_state(msg.payload):
            if (
                self._qbus_controller_state.properties
                and self._qbus_controller_state.properties.connectable is False
            ):
                _LOGGER.debug(
                    "Activating controller %s", self._qbus_controller_state.id
                )
                payload = json.dumps(
                    self._qbus_controller_state.activate_command.payload
                )
                topic = self._qbus_controller_state.activate_command.topic

                await mqtt.async_publish(self._hass, topic, payload)

    def shutdown(self, event: Event | None = None) -> None:
        """Shutdown Qbus Hub."""
        _LOGGER.debug("Shutting down hub")

        self._registered_entity_ids = []
        self._entry.state_queue.close()

    def remove(self) -> None:
        """Remove Qbus Hub."""
        _LOGGER.debug("Removing hub")

        self.shutdown()

    @callback
    async def _options_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        _LOGGER.debug("Update options %s", entry.entry_id)

        await hass.config_entries.async_reload(entry.entry_id)

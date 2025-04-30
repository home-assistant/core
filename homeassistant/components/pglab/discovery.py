"""Discovery PG LAB Electronics devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Any

from pypglab.device import Device as PyPGLabDevice
from pypglab.mqtt import Client as PyPGLabMqttClient

from homeassistant.components.mqtt import (
    EntitySubscription,
    ReceiveMessage,
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import DISCOVERY_TOPIC, DOMAIN, LOGGER
from .coordinator import PGLabSensorsCoordinator

if TYPE_CHECKING:
    from . import PGLabConfigEntry

# Supported platforms.
PLATFORMS = [
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Used to create a new component entity.
CREATE_NEW_ENTITY = {
    Platform.COVER: "pglab_create_new_entity_cover",
    Platform.SENSOR: "pglab_create_new_entity_sensor",
    Platform.SWITCH: "pglab_create_new_entity_switch",
}


class PGLabDiscoveryError(Exception):
    """Raised when a discovery has failed."""


def get_device_id_from_discovery_topic(topic: str) -> str | None:
    """From the discovery topic get the PG LAB Electronics device id."""

    # The discovery topic has the following format "pglab/discovery/[Device ID]/config"
    split_topic = topic.split("/", 5)

    # Do a sanity check on the string.
    if len(split_topic) != 4:
        return None

    if split_topic[3] != "config":
        return None

    return split_topic[2]


class DiscoverDeviceInfo:
    """Keeps information of the PGLab discovered device."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PGLabConfigEntry,
        pglab_device: PyPGLabDevice,
    ) -> None:
        """Initialize the device discovery info."""

        # Hash string represents the devices actual configuration,
        # it depends on the number of available relays and shutters.
        # When the hash string changes the devices entities must be rebuilt.
        self._hash = pglab_device.hash
        self._entities: list[tuple[str, str]] = []
        self.coordinator = PGLabSensorsCoordinator(hass, config_entry, pglab_device)

    def add_entity(self, platform_domain: str, entity_unique_id: str | None) -> None:
        """Add an entity."""

        # PGLabEntity always have unique IDs
        if TYPE_CHECKING:
            assert entity_unique_id is not None
        self._entities.append((platform_domain, entity_unique_id))

    @property
    def hash(self) -> int:
        """Return the hash for this configuration."""
        return self._hash

    @property
    def entities(self) -> list[tuple[str, str]]:
        """Return array of entities available."""
        return self._entities


async def create_discover_device_info(
    hass: HomeAssistant, config_entry: PGLabConfigEntry, pglab_device: PyPGLabDevice
) -> DiscoverDeviceInfo:
    """Create a new DiscoverDeviceInfo instance."""
    discovery_info = DiscoverDeviceInfo(hass, config_entry, pglab_device)

    # Subscribe to sensor state changes.
    await discovery_info.coordinator.subscribe_topics()
    return discovery_info


@dataclass
class PGLabDiscovery:
    """Discovery a PGLab device with the following MQTT topic format pglab/discovery/[device]/config."""

    def __init__(self) -> None:
        """Initialize the discovery class."""
        self._substate: dict[str, EntitySubscription] = {}
        self._discovery_topic = DISCOVERY_TOPIC
        self._mqtt_client = None
        self._discovered: dict[str, DiscoverDeviceInfo] = {}
        self._disconnect_platform: list = []

    async def __build_device(
        self, mqtt: PyPGLabMqttClient, msg: ReceiveMessage
    ) -> PyPGLabDevice:
        """Build a PGLab device."""

        # Check if the discovery message is in valid json format.
        try:
            payload = json.loads(msg.payload)
        except ValueError as err:
            raise PGLabDiscoveryError(
                f"Can't decode discovery payload: {msg.payload!r}"
            ) from err

        device_id = "id"

        # Check if the key id is present in the payload. It must always be present.
        if device_id not in payload:
            raise PGLabDiscoveryError(
                "Unexpected discovery payload format, id key not present"
            )

        # Do a sanity check: the id must match the discovery topic /pglab/discovery/[id]/config
        topic = msg.topic
        if not topic.endswith(f"{payload[device_id]}/config"):
            raise PGLabDiscoveryError("Unexpected discovery topic format")

        # Build and configure the PGLab device.
        pglab_device = PyPGLabDevice()
        if not await pglab_device.config(mqtt, payload):
            raise PGLabDiscoveryError("Error during setup of a new discovered device")

        return pglab_device

    def __clean_discovered_device(self, hass: HomeAssistant, device_id: str) -> None:
        """Destroy the device and any entities connected to the device."""

        if device_id not in self._discovered:
            return

        discovery_info = self._discovered[device_id]

        # Destroy all entities connected to the device.
        entity_registry = er.async_get(hass)
        for platform, unique_id in discovery_info.entities:
            if entity_id := entity_registry.async_get_entity_id(
                platform, DOMAIN, unique_id
            ):
                entity_registry.async_remove(entity_id)

        # Destroy the device.
        device_registry = dr.async_get(hass)
        if device_entry := device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        ):
            device_registry.async_remove_device(device_entry.id)

        # Clean the discovery info.
        del self._discovered[device_id]

    async def start(
        self,
        hass: HomeAssistant,
        mqtt: PyPGLabMqttClient,
        config_entry: PGLabConfigEntry,
    ) -> None:
        """Start discovering a PGLab devices."""

        async def discovery_message_received(msg: ReceiveMessage) -> None:
            """Received a new discovery message."""

            # Create a PGLab device and add entities.
            try:
                pglab_device = await self.__build_device(mqtt, msg)
            except PGLabDiscoveryError as err:
                LOGGER.warning("Can't create PGLabDiscovery instance(%s) ", str(err))

                # For some reason it's not possible to create the device with the discovery message,
                # be sure that any previous device with the same topic is now destroyed.
                device_id = get_device_id_from_discovery_topic(msg.topic)

                # If there is a valid topic device_id clean everything relative to the device.
                if device_id:
                    self.__clean_discovered_device(hass, device_id)

                return

            # Create a new device.
            device_registry = dr.async_get(hass)
            device_registry.async_get_or_create(
                config_entry_id=config_entry.entry_id,
                configuration_url=f"http://{pglab_device.ip}/",
                connections={(CONNECTION_NETWORK_MAC, pglab_device.mac)},
                identifiers={(DOMAIN, pglab_device.id)},
                manufacturer=pglab_device.manufacturer,
                model=pglab_device.type,
                name=pglab_device.name,
                sw_version=pglab_device.firmware_version,
                hw_version=pglab_device.hardware_version,
            )

            # Do some checking if previous entities must be updated.
            if pglab_device.id in self._discovered:
                # The device is already been discovered,
                # get the old discovery info data.
                discovery_info = self._discovered[pglab_device.id]

                if discovery_info.hash == pglab_device.hash:
                    # Best case, there is nothing to do.
                    # The device is still in the same configuration. Same name, same shutters, same relay etc.
                    return

                LOGGER.warning(
                    "Changed internal configuration of device(%s). Rebuilding all entities",
                    pglab_device.id,
                )

                # Something has changed, all previous entities must be destroyed and re-created.
                self.__clean_discovered_device(hass, pglab_device.id)

            # Add a new device.
            discovery_info = await create_discover_device_info(
                hass, config_entry, pglab_device
            )
            self._discovered[pglab_device.id] = discovery_info

            # Create all new cover entities.
            for s in pglab_device.shutters:
                # the HA entity is not yet created, send a message to create it
                async_dispatcher_send(
                    hass, CREATE_NEW_ENTITY[Platform.COVER], pglab_device, s
                )

            # Create all new relay entities.
            for r in pglab_device.relays:
                # The HA entity is not yet created, send a message to create it.
                async_dispatcher_send(
                    hass, CREATE_NEW_ENTITY[Platform.SWITCH], pglab_device, r
                )

            # Create all new sensor entities.
            async_dispatcher_send(
                hass,
                CREATE_NEW_ENTITY[Platform.SENSOR],
                pglab_device,
                discovery_info.coordinator,
            )

        topics = {
            "discovery_topic": {
                "topic": f"{self._discovery_topic}/#",
                "msg_callback": discovery_message_received,
            }
        }

        # Forward setup all HA supported platforms.
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

        self._mqtt_client = mqtt
        self._substate = async_prepare_subscribe_topics(hass, self._substate, topics)
        await async_subscribe_topics(hass, self._substate)

    async def register_platform(
        self, hass: HomeAssistant, platform: Platform, target: Callable[..., Any]
    ):
        """Register a callback to create entity of a specific HA platform."""
        disconnect_callback = async_dispatcher_connect(
            hass, CREATE_NEW_ENTITY[platform], target
        )
        self._disconnect_platform.append(disconnect_callback)

    async def stop(self, hass: HomeAssistant, config_entry: PGLabConfigEntry) -> None:
        """Stop to discovery PG LAB devices."""
        await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

        # Disconnect all registered platforms.
        for disconnect_callback in self._disconnect_platform:
            disconnect_callback()

        async_unsubscribe_topics(hass, self._substate)

    async def add_entity(
        self, platform_domain: str, entity_unique_id: str | None, device_id: str
    ):
        """Save a new PG LAB device entity."""

        # Be sure that the device is been discovered.
        if device_id not in self._discovered:
            raise PGLabDiscoveryError("Unknown device, device_id not discovered")

        discovery_info = self._discovered[device_id]
        discovery_info.add_entity(platform_domain, entity_unique_id)

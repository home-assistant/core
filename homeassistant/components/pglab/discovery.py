"""Discovery a PG LAB Electronics devices."""

import json

from pypglab.device import Device
from pypglab.mqtt import Client

from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.components.mqtt.subscription import (
    EntitySubscription,
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import (
    _LOGGER,
    CREATE_NEW_ENTITY,
    DEVICE_ALREADY_DISCOVERED,
    DISCOVERY_TOPIC,
    DOMAIN,
)


def GetDeviceIdFromDiscoveryTopic(topic: str) -> str | None:
    """From the discovery topic get the PG LAB Electronics device id."""

    # the discovery topi has the following format "pglab/discovery/[Device ID]/config"
    split_topic = topic.split("/")

    # do a sanity check on the string
    if len(split_topic) != 4:
        return None

    if split_topic[3] != "config":
        return None

    return split_topic[2]


def CleanDiscoveredDevice(hass: HomeAssistant, device_id: str) -> None:
    """Destroy the device and any enties connected with the device."""

    if device_id not in hass.data[DEVICE_ALREADY_DISCOVERED]:
        return

    discovery_info = hass.data[DEVICE_ALREADY_DISCOVERED][device_id]

    # destroy all entities connected with the device
    entity_registry = er.async_get(hass)
    for platform, entityid in discovery_info.entities:
        entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, entityid)
        if entity_id:
            entity_registry.async_remove(entity_id)

    # destroy the device
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    if device_entry:
        device_registry.async_remove_device(device_entry.id)

    # clean the discovery info
    del hass.data[DEVICE_ALREADY_DISCOVERED][device_id]


class DiscoverDeviceInfo:
    """It's keeping information of the PGLAB discovered device."""

    def __init__(self, pglab_device: Device) -> None:
        """Initialize the device discovery info."""

        # hash string that represent the device actual configuration,
        # it depends by the number of available relay and shutter
        # When changed the device enties must be rebuilt
        self._hash = pglab_device.hash
        self._entities: list[tuple[str, str]] = []

    def add_entity(self, entity: Entity) -> None:
        """Add the entity id."""
        if entity.unique_id:
            self._entities.append((entity.platform.domain, entity.unique_id))

    @property
    def hash(self) -> int:
        """Return the hash for this configuration."""
        return self._hash

    @property
    def entities(self) -> list[tuple[str, str]]:
        """Return array of entities available."""
        return self._entities


class Discovery:
    """PG LAB Discovery class. Discovery a pglab/discovert/[device]/config."""

    def __init__(self) -> None:
        """Initialize the discovery class."""
        self._substate: dict[str, EntitySubscription] = {}
        self._discovery_topic = DISCOVERY_TOPIC
        self._mqtt_client = None

    async def __build_device(self, mqtt: Client, msg: ReceiveMessage) -> Device:
        # check if the discovery message is in valid jason format
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            _LOGGER.warning("Can't decode discovery payload: %s", msg.payload)
            return None

        device_id = "id"

        # check the key id is present in the paylod. It must always present !!!
        if device_id not in payload:
            _LOGGER.warning("Unexpected discovery payload format, id key not present")
            return None

        # do a sanity check: the id must match the discovery topic /pglab/discovery/[id]/config
        topic = msg.topic
        if not topic.endswith(f"{payload[device_id]}/config"):
            return None

        # build and configure the PG LAB device
        pglab_device = Device()
        if not await pglab_device.config(mqtt, payload):
            _LOGGER.warning("Error during setup of new discovered device")
            return None

        return pglab_device

    async def start(
        self, hass: HomeAssistant, mqtt: Client, entry: ConfigEntry
    ) -> None:
        """Start to discovery a device."""

        async def discovery_message_received(msg: ReceiveMessage) -> None:
            """Received a new discovery message."""

            # create a PG LAB device and add in HA all the available entities
            pglab_device = await self.__build_device(mqtt, msg)

            if not pglab_device:
                # for some reason it's not possible to create the device with the discovery message
                # be sure that any previous device with the same topic are now destroy
                device_id = GetDeviceIdFromDiscoveryTopic(msg.topic)

                # if we have a valid topic device_id clean every thing relative to the device
                if device_id:
                    CleanDiscoveredDevice(hass, device_id)

                return

            # we can create a new device now
            device_registry = dr.async_get(hass)
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                configuration_url=f"http://{pglab_device.ip}/",
                connections={(CONNECTION_NETWORK_MAC, pglab_device.mac)},
                identifiers={(DOMAIN, pglab_device.id)},
                manufacturer=pglab_device.manufactor,
                model=pglab_device.type,
                name=pglab_device.name,
                sw_version=pglab_device.firmware_version,
                hw_version=pglab_device.hardware_version,
            )

            # do some checking if previous entities must be updated
            if pglab_device.id in hass.data[DEVICE_ALREADY_DISCOVERED]:
                # the device is already been discover
                # get the old discovery info data
                discovery_info = hass.data[DEVICE_ALREADY_DISCOVERED][pglab_device.id]

                if discovery_info.hash == pglab_device.hash:
                    # best case!!! there is nothing to do ... the device
                    # is still  in the same configuration. Same name, same shutters, same relay etc...
                    return None

                _LOGGER.info(
                    "Changed internal configuration of device(%s). Rebuilding all entities",
                    pglab_device.id,
                )

                # something is changed ... all previous entities must be destroy and re-create
                CleanDiscoveredDevice(hass, pglab_device.id)

            # add a new device
            discovery_info = DiscoverDeviceInfo(pglab_device)
            hass.data[DEVICE_ALREADY_DISCOVERED][pglab_device.id] = discovery_info

            # create all new relay entities
            for r in pglab_device.relays:
                # the HA entity is not yet created, send a message to create it
                async_dispatcher_send(
                    hass, CREATE_NEW_ENTITY[Platform.SWITCH], pglab_device, r
                )

        topics = {
            "discovery_topic": {
                "topic": f"{self._discovery_topic}/#",
                "msg_callback": discovery_message_received,
            }
        }

        self._mqtt_client = mqtt
        self._substate = async_prepare_subscribe_topics(hass, self._substate, topics)
        await async_subscribe_topics(hass, self._substate)

    async def stop(self, hass: HomeAssistant) -> None:
        """Stop to discovery a device."""
        async_unsubscribe_topics(hass, self._substate)


# create an instance of the discovery PG LAB devices
async def CreateDiscovery(
    hass: HomeAssistant, entry: ConfigEntry, mqtt: Client
) -> Discovery:
    """Create and initialize a discovery instance."""

    discovery = Discovery()
    await discovery.start(hass, mqtt, entry)
    return discovery
